import json
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models.users import User
from db.models.finance import (
    UserSkill, XpHistory,
    Lesson, UserLesson,
    Challenge, UserChallenge, Achievement, UserAchievement,
    MarketItem, UserMarketItem,
)
from shared.dependencies import get_current_user
from shared.finance_seed import get_or_init_profile, get_level_info, MONTHS_RU
from gamificationapp.src.schemas import (
    TreeLevelResponse,
    SkillResponse,
    XpHistoryItem,
    StreakResponse,
    CurrencyResponse,
    LessonResponse, LessonCompleteResponse,
    ChallengeResponse, ChallengeCompleteResponse,
    AchievementResponse,
    GrowthStage, MarketItemResponse,
)

router = APIRouter(tags=["gamification"])


# ─── Tree / XP ───────────────────────────────────────────────────────────────

@router.get("/user/tree", response_model=TreeLevelResponse)
async def get_user_tree(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> TreeLevelResponse:
    profile = await get_or_init_profile(current_user.user_uuid, db)
    info = get_level_info(profile.xp_total)
    return TreeLevelResponse(
        **info,
        growthPoints=profile.growth_points,
        financialScore=profile.financial_score,
    )


@router.get("/user/skills", response_model=list[SkillResponse])
async def get_user_skills(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[SkillResponse]:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    skills = (await db.execute(select(UserSkill).where(UserSkill.user_uuid == uid))).scalars().all()
    return [SkillResponse(label=s.label, value=s.value, color=s.color) for s in skills]


@router.get("/user/xp/history", response_model=list[XpHistoryItem])
async def get_xp_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    months: int = 6,
) -> list[XpHistoryItem]:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    history = (await db.execute(
        select(XpHistory).where(XpHistory.user_uuid == uid)
    )).scalars().all()

    # Сортируем так, чтобы текущий месяц был последним.
    # month_order[month_name] = позиция от 0 (12 мес назад) до 11 (текущий)
    now = datetime.utcnow()
    month_order = {MONTHS_RU[(now.month - i - 1) % 12]: i for i in range(12)}
    sorted_history = sorted(history, key=lambda h: month_order.get(h.month, 99), reverse=True)
    return [XpHistoryItem(month=h.month, value=h.value) for h in sorted_history[-months:]]


@router.get("/user/streak", response_model=StreakResponse)
async def get_streak(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StreakResponse:
    profile = await get_or_init_profile(current_user.user_uuid, db)
    now = datetime.utcnow()
    reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    delta = reset_time - now
    return StreakResponse(
        streakDays=profile.streak_days,
        resetHours=int(delta.total_seconds() // 3600),
        resetMinutes=int((delta.total_seconds() % 3600) // 60),
    )


@router.get("/user/currency", response_model=CurrencyResponse)
async def get_currency(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CurrencyResponse:
    profile = await get_or_init_profile(current_user.user_uuid, db)
    return CurrencyResponse(xp=profile.xp_total, gems=profile.gems)


# ─── Lessons ─────────────────────────────────────────────────────────────────

@router.get("/lessons", response_model=list[LessonResponse])
async def get_lessons(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[LessonResponse]:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)

    lessons = (await db.execute(select(Lesson).order_by(Lesson.number))).scalars().all()
    user_lessons = {
        ul.lesson_id: ul
        for ul in (await db.execute(
            select(UserLesson).where(UserLesson.user_uuid == uid)
        )).scalars().all()
    }
    result = []
    for lesson in lessons:
        ul = user_lessons.get(lesson.id)
        status = ul.status if ul else "locked"
        result.append(LessonResponse(
            id=lesson.id,
            number=lesson.number,
            title=lesson.title,
            subtitle=lesson.subtitle,
            description=lesson.description,
            xp=lesson.xp,
            duration=lesson.duration,
            status=status,
            progress=ul.progress if (ul and status == "in-progress") else None,
        ))
    return result


@router.get("/lessons/current", response_model=LessonResponse)
async def get_current_lesson(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> LessonResponse:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    ul = (await db.execute(
        select(UserLesson).where(and_(UserLesson.user_uuid == uid, UserLesson.status == "in-progress"))
    )).scalars().first()
    if not ul:
        raise HTTPException(status_code=404, detail="No lesson in progress")
    lesson = await db.get(Lesson, ul.lesson_id)
    return LessonResponse(
        id=lesson.id,
        number=lesson.number,
        title=lesson.title,
        subtitle=lesson.subtitle,
        description=lesson.description,
        xp=lesson.xp,
        duration=lesson.duration,
        status=ul.status,
        progress=ul.progress,
    )


@router.patch("/lessons/{lesson_id}/complete", response_model=LessonCompleteResponse)
async def complete_lesson(
    lesson_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> LessonCompleteResponse:
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    ul = (await db.execute(
        select(UserLesson).where(and_(UserLesson.user_uuid == uid, UserLesson.lesson_id == lesson_id))
    )).scalars().first()

    if ul and ul.status == "completed":
        return LessonCompleteResponse(ok=True, xpEarned=0)

    if ul:
        ul.status = "completed"
        ul.progress = 100
    else:
        db.add(UserLesson(user_uuid=uid, lesson_id=lesson_id, status="completed", progress=100))

    next_lesson = (await db.execute(
        select(Lesson).where(Lesson.number == lesson.number + 1)
    )).scalars().first()
    if next_lesson:
        next_ul = (await db.execute(
            select(UserLesson).where(and_(UserLesson.user_uuid == uid, UserLesson.lesson_id == next_lesson.id))
        )).scalars().first()
        if next_ul:
            if next_ul.status == "locked":
                next_ul.status = "in-progress"
        else:
            db.add(UserLesson(user_uuid=uid, lesson_id=next_lesson.id, status="in-progress"))

    profile.xp += lesson.xp
    profile.xp_total += lesson.xp
    await db.commit()
    return LessonCompleteResponse(ok=True, xpEarned=lesson.xp)


# ─── Challenges ──────────────────────────────────────────────────────────────

@router.get("/challenges/daily", response_model=list[ChallengeResponse])
async def get_daily_challenges(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[ChallengeResponse]:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    return await _get_challenges_by_type(uid, "daily", db)


@router.get("/challenges/weekly", response_model=ChallengeResponse)
async def get_weekly_challenge(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ChallengeResponse:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    items = await _get_challenges_by_type(uid, "weekly", db)
    if not items:
        raise HTTPException(status_code=404, detail="No weekly challenge")
    return items[0]


@router.get("/challenges/ai", response_model=list[ChallengeResponse])
async def get_ai_challenges(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[ChallengeResponse]:
    uid = current_user.user_uuid
    rows = (await db.execute(
        select(Challenge, UserChallenge)
        .join(UserChallenge, and_(
            UserChallenge.challenge_id == Challenge.id,
            UserChallenge.user_uuid == uid,
        ))
        .where(Challenge.type == "ai")
        .order_by(UserChallenge.id)
    )).all()
    return [
        ChallengeResponse(
            id=ch.id,
            title=ch.title,
            description=ch.description,
            progress=uc.progress,
            total=ch.total,
            reward=ch.reward,
            status=uc.status,
        )
        for ch, uc in rows
    ]


@router.post("/challenges/{challenge_id}/complete", response_model=ChallengeCompleteResponse)
async def complete_challenge(
    challenge_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ChallengeCompleteResponse:
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)

    uc = (await db.execute(
        select(UserChallenge).where(
            and_(UserChallenge.user_uuid == uid, UserChallenge.challenge_id == challenge_id)
        )
    )).scalars().first()
    if not uc:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge = await db.get(Challenge, challenge_id)
    if uc.status == "completed":
        return ChallengeCompleteResponse(ok=True, xpEarned=0)

    uc.progress = min(uc.progress + 1, challenge.total)
    if uc.progress >= challenge.total:
        uc.status = "completed"
        profile.xp += challenge.reward
        profile.xp_total += challenge.reward

    await db.commit()
    return ChallengeCompleteResponse(
        ok=True,
        xpEarned=challenge.reward if uc.status == "completed" else 0,
    )


async def _get_challenges_by_type(uid, type_: str, db: AsyncSession) -> list[ChallengeResponse]:
    challenges = (await db.execute(select(Challenge).where(Challenge.type == type_))).scalars().all()
    user_challenges = {
        uc.challenge_id: uc
        for uc in (await db.execute(
            select(UserChallenge).where(UserChallenge.user_uuid == uid)
        )).scalars().all()
    }
    return [
        ChallengeResponse(
            id=ch.id,
            title=ch.title,
            description=ch.description,
            progress=user_challenges[ch.id].progress if ch.id in user_challenges else 0,
            total=ch.total,
            reward=ch.reward,
            status=user_challenges[ch.id].status if ch.id in user_challenges else "pending",
        )
        for ch in challenges
    ]


# ─── Achievements ────────────────────────────────────────────────────────────

@router.get("/achievements", response_model=list[AchievementResponse])
async def get_achievements(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[AchievementResponse]:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    achievements = (await db.execute(select(Achievement))).scalars().all()
    user_achievements = {
        ua.achievement_id: ua
        for ua in (await db.execute(
            select(UserAchievement).where(UserAchievement.user_uuid == uid)
        )).scalars().all()
    }
    return [
        AchievementResponse(
            id=a.id,
            title=a.title,
            description=a.description,
            unlocked=user_achievements[a.id].unlocked if a.id in user_achievements else False,
        )
        for a in achievements
    ]


# ─── Market ──────────────────────────────────────────────────────────────────

@router.get("/market/items", response_model=list[MarketItemResponse])
async def get_market_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    category: Optional[Literal['trees', 'decor', 'boosts']] = None,
) -> list[MarketItemResponse]:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    q = select(MarketItem)
    if category:
        q = q.where(MarketItem.category == category)
    items = (await db.execute(q)).scalars().all()
    user_items = {
        ui.item_id: ui
        for ui in (await db.execute(
            select(UserMarketItem).where(UserMarketItem.user_uuid == uid)
        )).scalars().all()
    }
    return [_build_market_response(item, user_items.get(item.id)) for item in items]


@router.post("/market/items/{item_id}/buy", response_model=MarketItemResponse)
async def buy_market_item(
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MarketItemResponse:
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    item = await db.get(MarketItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    ui = (await db.execute(
        select(UserMarketItem).where(and_(UserMarketItem.user_uuid == uid, UserMarketItem.item_id == item_id))
    )).scalars().first()

    if ui and ui.owned:
        raise HTTPException(status_code=400, detail="Already owned")

    if item.currency == "xp":
        if profile.xp_total < item.cost:
            raise HTTPException(status_code=400, detail="Not enough XP")
        profile.xp_total -= item.cost
        profile.xp = max(0, profile.xp - item.cost)
    else:
        if profile.gems < item.cost:
            raise HTTPException(status_code=400, detail="Not enough gems")
        profile.gems -= item.cost

    if ui:
        ui.owned = True
    else:
        ui = UserMarketItem(user_uuid=uid, item_id=item_id, owned=True)
        db.add(ui)

    await db.commit()
    await db.refresh(ui)
    return _build_market_response(item, ui)


@router.patch("/market/items/{item_id}/equip", response_model=MarketItemResponse)
async def equip_market_item(
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MarketItemResponse:
    uid = current_user.user_uuid
    ui = (await db.execute(
        select(UserMarketItem).where(and_(UserMarketItem.user_uuid == uid, UserMarketItem.item_id == item_id))
    )).scalars().first()
    if not ui or not ui.owned:
        raise HTTPException(status_code=400, detail="Item not owned")

    item = await db.get(MarketItem, item_id)
    if item and item.category == "trees":
        other_trees = (await db.execute(
            select(UserMarketItem)
            .join(MarketItem, UserMarketItem.item_id == MarketItem.id)
            .where(and_(UserMarketItem.user_uuid == uid, MarketItem.category == "trees",
                        UserMarketItem.active == True))
        )).scalars().all()
        for t in other_trees:
            t.active = False

    ui.active = not ui.active
    await db.commit()
    return _build_market_response(item, ui)


def _build_market_response(item: MarketItem, ui: Optional[UserMarketItem]) -> MarketItemResponse:
    try:
        stages_raw = json.loads(item.stages_json)
        stages = [GrowthStage(**s) for s in stages_raw]
    except Exception:
        stages = []
    return MarketItemResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        cost=item.cost,
        currency=item.currency,
        color=item.color,
        emoji=item.emoji,
        category=item.category,
        isNew=item.is_new,
        stages=stages,
        owned=ui.owned if ui else False,
        active=ui.active if ui else False,
    )
