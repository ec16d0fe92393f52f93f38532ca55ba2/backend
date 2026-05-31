import json
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models.users import User
from db.models.finance import (
    Transaction, Category, UserProfile, XpHistory, UserSkill,
    Goal, Milestone, MilestoneSubtask,
    Lesson, UserLesson,
    Challenge, UserChallenge, Achievement, UserAchievement,
    MarketItem, UserMarketItem, SavingsGoal,
)
from authapp.src.dependencies import get_current_user
from authapp.src.seed import get_or_init_profile, get_level_info, MONTHS_RU

router = APIRouter(tags=["finance"])


# ──────────────────────────── Schemas ────────────────────────────

class TransactionCreate(BaseModel):
    title: str
    amount: float
    category: str
    type: str
    date: Optional[str] = None


class GoalCreate(BaseModel):
    title: str
    target: float
    deadline: str


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    current: Optional[float] = None
    target: Optional[float] = None
    deadline: Optional[str] = None


class MilestoneUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None


class SubtaskUpdate(BaseModel):
    done: bool


class BudgetLimitUpdate(BaseModel):
    monthlyLimit: float


class SavingsGoalCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    icon: Optional[str] = "💰"
    target: float


class MarketBuyBody(BaseModel):
    pass


# ──────────────────────────── Balance ────────────────────────────

@router.get("/balance")
async def get_balance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)

    income = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "income"))
    )).scalar()

    expenses = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense"))
    )).scalar()

    saved = (await db.execute(
        select(func.coalesce(func.sum(SavingsGoal.current), 0))
        .where(SavingsGoal.user_uuid == uid)
    )).scalar()

    return {"total": income - expenses, "income": income, "expenses": expenses, "saved": saved}


# ──────────────────────────── Transactions ────────────────────────────

@router.get("/transactions")
async def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    type: Optional[str] = None,
    limit: Optional[int] = None,
    date: Optional[str] = None,
):
    uid = current_user.user_uuid
    q = select(Transaction).where(Transaction.user_uuid == uid).order_by(Transaction.date.desc())
    if type:
        q = q.where(Transaction.type == type)
    if date:
        try:
            day = datetime.fromisoformat(date).date()
            q = q.where(func.date(Transaction.date) == day)
        except ValueError:
            pass
    if limit:
        q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [_tx_dict(t) for t in rows]


@router.post("/transactions")
async def create_transaction(
    body: TransactionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)

    date = datetime.fromisoformat(body.date) if body.date else datetime.utcnow()
    tx = Transaction(
        user_uuid=uid,
        title=body.title,
        amount=body.amount,
        category=body.category,
        type=body.type,
        date=date,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return _tx_dict(tx)


@router.delete("/transactions/{tx_id}")
async def delete_transaction(
    tx_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    tx = await db.get(Transaction, tx_id)
    if not tx or tx.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.delete(tx)
    await db.commit()
    return {"ok": True}


def _tx_dict(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "amount": t.amount,
        "category": t.category,
        "type": t.type,
        "date": t.date.isoformat(),
    }


# ──────────────────────────── Categories ────────────────────────────

@router.get("/categories/expense")
async def get_expense_categories(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Category).where(Category.type == "expense"))).scalars().all()
    return [{"id": c.id, "label": c.label, "emoji": c.emoji} for c in rows]


@router.get("/categories/income")
async def get_income_categories(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Category).where(Category.type == "income"))).scalars().all()
    return [{"id": c.id, "label": c.label, "emoji": c.emoji} for c in rows]


# ──────────────────────────── Tree / XP ────────────────────────────

@router.get("/user/tree")
async def get_user_tree(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    info = get_level_info(profile.xp_total)
    return {
        **info,
        "growthPoints": profile.growth_points,
        "financialScore": profile.financial_score,
    }


@router.get("/user/skills")
async def get_user_skills(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    skills = (await db.execute(
        select(UserSkill).where(UserSkill.user_uuid == uid)
    )).scalars().all()
    return [{"label": s.label, "value": s.value, "color": s.color} for s in skills]


@router.get("/user/xp/history")
async def get_xp_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    months: int = 6,
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    history = (await db.execute(
        select(XpHistory).where(XpHistory.user_uuid == uid).order_by(XpHistory.id)
    )).scalars().all()
    return [{"month": h.month, "value": h.value} for h in history[-months:]]


@router.get("/user/streak")
async def get_streak(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    now = datetime.utcnow()
    reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    delta = reset_time - now
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    return {"streakDays": profile.streak_days, "resetHours": hours, "resetMinutes": minutes}


@router.get("/user/currency")
async def get_currency(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    return {"xp": profile.xp_total, "gems": profile.gems}


# ──────────────────────────── Goals ────────────────────────────

@router.get("/goals")
async def get_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    goals = (await db.execute(select(Goal).where(Goal.user_uuid == uid))).scalars().all()
    return [_goal_dict(g) for g in goals]


@router.post("/goals")
async def create_goal(
    body: GoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goal = Goal(user_uuid=current_user.user_uuid, **body.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return _goal_dict(goal)


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goal = await db.get(Goal, goal_id)
    if not goal or goal.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(goal, field, val)
    await db.commit()
    await db.refresh(goal)
    return _goal_dict(goal)


@router.get("/goals/{goal_id}/milestones")
async def get_milestones(
    goal_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goal = await db.get(Goal, goal_id)
    if not goal or goal.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = (await db.execute(
        select(Milestone).where(Milestone.goal_id == goal_id)
    )).scalars().all()
    result = []
    for m in milestones:
        subtasks = (await db.execute(
            select(MilestoneSubtask).where(MilestoneSubtask.milestone_id == m.id)
        )).scalars().all()
        result.append(_milestone_dict(m, subtasks))
    return result


@router.patch("/goals/{goal_id}/milestones/{milestone_id}")
async def update_milestone(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goal = await db.get(Goal, goal_id)
    if not goal or goal.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestone = await db.get(Milestone, milestone_id)
    if not milestone or milestone.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Milestone not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(milestone, field, val)
    await db.commit()
    subtasks = (await db.execute(
        select(MilestoneSubtask).where(MilestoneSubtask.milestone_id == milestone_id)
    )).scalars().all()
    return _milestone_dict(milestone, subtasks)


@router.patch("/goals/{goal_id}/milestones/{milestone_id}/subtasks/{subtask_id}")
async def toggle_subtask(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    subtask_id: uuid.UUID,
    body: SubtaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goal = await db.get(Goal, goal_id)
    if not goal or goal.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Goal not found")
    subtask = await db.get(MilestoneSubtask, subtask_id)
    if not subtask or subtask.milestone_id != milestone_id:
        raise HTTPException(status_code=404, detail="Subtask not found")
    subtask.done = body.done
    await db.commit()
    return {"id": str(subtask.id), "text": subtask.text, "done": subtask.done}


def _goal_dict(g: Goal) -> dict:
    return {"id": str(g.id), "title": g.title, "current": g.current, "target": g.target, "deadline": g.deadline}


def _milestone_dict(m: Milestone, subtasks) -> dict:
    return {
        "id": str(m.id),
        "title": m.title,
        "description": m.description,
        "date": m.date,
        "xp": m.xp,
        "status": m.status,
        "subtasks": [{"id": str(s.id), "text": s.text, "done": s.done} for s in subtasks],
    }


# ──────────────────────────── Lessons ────────────────────────────

@router.get("/lessons")
async def get_lessons(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
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
        progress = ul.progress if ul else 0
        item = {
            "id": str(lesson.id),
            "number": lesson.number,
            "title": lesson.title,
            "subtitle": lesson.subtitle,
            "description": lesson.description,
            "xp": lesson.xp,
            "duration": lesson.duration,
            "status": status,
        }
        if status == "in-progress":
            item["progress"] = progress
        result.append(item)
    return result


@router.get("/lessons/current")
async def get_current_lesson(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)

    ul = (await db.execute(
        select(UserLesson).where(and_(UserLesson.user_uuid == uid, UserLesson.status == "in-progress"))
    )).scalars().first()
    if not ul:
        raise HTTPException(status_code=404, detail="No lesson in progress")
    lesson = await db.get(Lesson, ul.lesson_id)
    return {
        "id": str(lesson.id),
        "number": lesson.number,
        "title": lesson.title,
        "subtitle": lesson.subtitle,
        "description": lesson.description,
        "xp": lesson.xp,
        "duration": lesson.duration,
        "status": ul.status,
        "progress": ul.progress,
    }


@router.patch("/lessons/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    ul = (await db.execute(
        select(UserLesson).where(and_(UserLesson.user_uuid == uid, UserLesson.lesson_id == lesson_id))
    )).scalars().first()
    if ul and ul.status == "completed":
        return {"ok": True, "xpEarned": 0}

    if ul:
        ul.status = "completed"
        ul.progress = 100
    else:
        db.add(UserLesson(user_uuid=uid, lesson_id=lesson_id, status="completed", progress=100))

    # Unlock next lesson
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

    # Award XP
    profile.xp += lesson.xp
    profile.xp_total += lesson.xp
    await db.commit()
    return {"ok": True, "xpEarned": lesson.xp}


# ──────────────────────────── Challenges ────────────────────────────

@router.get("/challenges/daily")
async def get_daily_challenges(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    return await _get_challenges_by_type(uid, "daily", db)


@router.get("/challenges/weekly")
async def get_weekly_challenge(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    items = await _get_challenges_by_type(uid, "weekly", db)
    if not items:
        raise HTTPException(status_code=404, detail="No weekly challenge")
    return items[0]


@router.post("/challenges/{challenge_id}/complete")
async def complete_challenge(
    challenge_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
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
        return {"ok": True, "xpEarned": 0}

    uc.progress = min(uc.progress + 1, challenge.total)
    if uc.progress >= challenge.total:
        uc.status = "completed"
        profile.xp += challenge.reward
        profile.xp_total += challenge.reward
        await db.commit()
        return {"ok": True, "xpEarned": challenge.reward}

    await db.commit()
    return {"ok": True, "xpEarned": 0}


async def _get_challenges_by_type(uid, type_: str, db: AsyncSession) -> list:
    challenges = (await db.execute(select(Challenge).where(Challenge.type == type_))).scalars().all()
    user_challenges = {
        uc.challenge_id: uc
        for uc in (await db.execute(
            select(UserChallenge).where(UserChallenge.user_uuid == uid)
        )).scalars().all()
    }
    result = []
    for ch in challenges:
        uc = user_challenges.get(ch.id)
        result.append({
            "id": str(ch.id),
            "title": ch.title,
            "description": ch.description,
            "progress": uc.progress if uc else 0,
            "total": ch.total,
            "reward": ch.reward,
            "status": uc.status if uc else "pending",
        })
    return result


# ──────────────────────────── Achievements ────────────────────────────

@router.get("/achievements")
async def get_achievements(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
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
        {
            "id": str(a.id),
            "title": a.title,
            "description": a.description,
            "unlocked": user_achievements[a.id].unlocked if a.id in user_achievements else False,
        }
        for a in achievements
    ]


# ──────────────────────────── Market ────────────────────────────

@router.get("/market/items")
async def get_market_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = None,
):
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
    return [_market_item_dict(item, user_items.get(item.id)) for item in items]


@router.post("/market/items/{item_id}/buy")
async def buy_market_item(
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
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
        db.add(UserMarketItem(user_uuid=uid, item_id=item_id, owned=True))

    await db.commit()
    await db.refresh(item)
    ui_fresh = (await db.execute(
        select(UserMarketItem).where(and_(UserMarketItem.user_uuid == uid, UserMarketItem.item_id == item_id))
    )).scalars().first()
    return _market_item_dict(item, ui_fresh)


@router.patch("/market/items/{item_id}/equip")
async def equip_market_item(
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    ui = (await db.execute(
        select(UserMarketItem).where(and_(UserMarketItem.user_uuid == uid, UserMarketItem.item_id == item_id))
    )).scalars().first()
    if not ui or not ui.owned:
        raise HTTPException(status_code=400, detail="Item not owned")

    item = await db.get(MarketItem, item_id)
    if item and item.category == "trees":
        # Unequip all other trees
        other_trees = (await db.execute(
            select(UserMarketItem)
            .join(MarketItem, UserMarketItem.item_id == MarketItem.id)
            .where(and_(UserMarketItem.user_uuid == uid, MarketItem.category == "trees", UserMarketItem.active == True))
        )).scalars().all()
        for t in other_trees:
            t.active = False

    ui.active = not ui.active
    await db.commit()
    return _market_item_dict(item, ui)


def _market_item_dict(item: MarketItem, ui: Optional[UserMarketItem]) -> dict:
    try:
        stages = json.loads(item.stages_json)
    except Exception:
        stages = []
    return {
        "id": str(item.id),
        "name": item.name,
        "description": item.description,
        "cost": item.cost,
        "currency": item.currency,
        "color": item.color,
        "emoji": item.emoji,
        "category": item.category,
        "isNew": item.is_new,
        "stages": stages,
        "owned": ui.owned if ui else False,
        "active": ui.active if ui else False,
    }


# ──────────────────────────── Budget ────────────────────────────

@router.get("/budget")
async def get_budget(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_expenses = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense", Transaction.date >= month_start))
    )).scalar()

    goals = (await db.execute(select(SavingsGoal).where(SavingsGoal.user_uuid == uid))).scalars().all()

    return {
        "monthlyLimit": profile.monthly_limit,
        "monthlyPlan": {
            "target": profile.monthly_limit,
            "projected": month_expenses,
        },
        "goals": [_savings_goal_dict(g) for g in goals],
        "treeLeaves": profile.tree_leaves,
        "leavesToNext": profile.leaves_to_next,
    }


@router.patch("/budget/limit")
async def update_budget_limit(
    body: BudgetLimitUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)
    profile.monthly_limit = body.monthlyLimit
    await db.commit()
    return {"monthlyLimit": profile.monthly_limit}


@router.get("/budget/goals")
async def get_savings_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    goals = (await db.execute(select(SavingsGoal).where(SavingsGoal.user_uuid == uid))).scalars().all()
    return [_savings_goal_dict(g) for g in goals]


@router.post("/budget/goals")
async def create_savings_goal(
    body: SavingsGoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goal = SavingsGoal(user_uuid=current_user.user_uuid, **body.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return _savings_goal_dict(goal)


def _savings_goal_dict(g: SavingsGoal) -> dict:
    return {
        "id": str(g.id),
        "title": g.title,
        "description": g.description,
        "icon": g.icon,
        "current": g.current,
        "target": g.target,
    }


# ──────────────────────────── Analytics ────────────────────────────

@router.get("/analytics/monthly")
async def get_monthly_analytics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    months: int = 6,
):
    uid = current_user.user_uuid
    now = datetime.utcnow()
    result = []
    for i in range(months - 1, -1, -1):
        start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            end = now
        else:
            next_month = (start.replace(day=28) + timedelta(days=4))
            end = next_month.replace(day=1)

        income = (await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(and_(Transaction.user_uuid == uid, Transaction.type == "income",
                        Transaction.date >= start, Transaction.date < end))
        )).scalar()

        expense = (await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense",
                        Transaction.date >= start, Transaction.date < end))
        )).scalar()

        result.append({
            "month": MONTHS_RU[start.month - 1],
            "income": income,
            "expense": expense,
        })
    return result


@router.get("/analytics/expenses/by-category")
async def get_expenses_by_category(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.user_uuid
    rows = (await db.execute(
        select(Transaction.category, func.sum(Transaction.amount).label("total"))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense"))
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
    )).all()

    categories = {
        c.id: c for c in (await db.execute(select(Category).where(Category.type == "expense"))).scalars().all()
    }
    return [
        {
            "label": categories[r.category].label if r.category in categories else r.category,
            "value": r.total,
            "color": categories[r.category].color if r.category in categories else "#90A4AE",
        }
        for r in rows
    ]
