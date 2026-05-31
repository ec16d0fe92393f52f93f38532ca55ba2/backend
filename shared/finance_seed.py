import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from db.models.finance import (
    Category, Lesson, Challenge, Achievement, MarketItem,
    UserProfile, UserSkill, XpHistory, UserLesson, UserChallenge,
    UserAchievement, UserMarketItem,
)

MONTHS_RU = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]

LEVEL_THRESHOLDS = [0, 100, 300, 700, 1500, 3000, 5000]
LEVEL_LABELS = ["Семя", "Росток", "Саженец", "Молодое дерево", "Дерево", "Дуб", "Секвойя"]

SEED_CATEGORIES = [
    {"id": "salary", "label": "Зарплата", "emoji": "💼", "type": "income", "color": "#4CAF50"},
    {"id": "freelance", "label": "Фриланс", "emoji": "💻", "type": "income", "color": "#2196F3"},
    {"id": "investment_in", "label": "Инвестиции", "emoji": "📈", "type": "income", "color": "#9C27B0"},
    {"id": "gift_income", "label": "Подарки", "emoji": "🎁", "type": "income", "color": "#E91E63"},
    {"id": "other_income", "label": "Другое", "emoji": "✨", "type": "income", "color": "#607D8B"},
    {"id": "food", "label": "Еда", "emoji": "🍔", "type": "expense", "color": "#FF6B6B"},
    {"id": "transport", "label": "Транспорт", "emoji": "🚗", "type": "expense", "color": "#4ECDC4"},
    {"id": "entertainment", "label": "Развлечения", "emoji": "🎮", "type": "expense", "color": "#FFE66D"},
    {"id": "health", "label": "Здоровье", "emoji": "💊", "type": "expense", "color": "#A8E6CF"},
    {"id": "clothes", "label": "Одежда", "emoji": "👗", "type": "expense", "color": "#FF8B94"},
    {"id": "education", "label": "Образование", "emoji": "📚", "type": "expense", "color": "#6C63FF"},
    {"id": "utilities", "label": "ЖКХ", "emoji": "🏠", "type": "expense", "color": "#FFA726"},
    {"id": "other_expense", "label": "Другое", "emoji": "📦", "type": "expense", "color": "#90A4AE"},
]

SEED_LESSONS = [
    {"number": 1, "title": "Основы бюджетирования", "subtitle": "С чего начать?", "description": "Как правильно планировать бюджет и контролировать расходы.", "xp": 50, "duration": 10},
    {"number": 2, "title": "Правило 50/30/20", "subtitle": "Простая формула", "description": "Распределение доходов на необходимое, желаемое и накопления.", "xp": 75, "duration": 15},
    {"number": 3, "title": "Экстренный фонд", "subtitle": "Ваша финансовая подушка", "description": "Почему важно иметь резервный фонд и как его создать.", "xp": 100, "duration": 20},
    {"number": 4, "title": "Инвестиции для начинающих", "subtitle": "Первые шаги", "description": "Акции, облигации, ETF — введение в мир инвестиций.", "xp": 150, "duration": 25},
    {"number": 5, "title": "Психология денег", "subtitle": "Мышление богатых", "description": "Как убеждения влияют на финансовые решения.", "xp": 125, "duration": 20},
    {"number": 6, "title": "Пассивный доход", "subtitle": "Деньги работают за вас", "description": "Стратегии создания пассивного дохода.", "xp": 200, "duration": 30},
]

SEED_CHALLENGES = [
    {"title": "Запись расходов", "description": "Запишите 3 расхода сегодня", "total": 3, "reward": 20, "type": "daily"},
    {"title": "Чек-ин бюджета", "description": "Проверьте состояние вашего бюджета", "total": 1, "reward": 15, "type": "daily"},
    {"title": "Урок дня", "description": "Пройдите хотя бы один урок", "total": 1, "reward": 25, "type": "daily"},
    {"title": "Неделя без спонтанных трат", "description": "Придерживайтесь плана все 7 дней", "total": 7, "reward": 100, "type": "weekly"},
]

SEED_ACHIEVEMENTS = [
    {"title": "Первый шаг", "description": "Записали первую транзакцию"},
    {"title": "На верном пути", "description": "7 дней подряд без пропусков"},
    {"title": "Знаток финансов", "description": "Прошли первый урок"},
    {"title": "Экономный", "description": "Накопили 10% от дохода за месяц"},
    {"title": "Инвестор", "description": "Первая инвестиционная транзакция"},
]

SEED_MARKET_ITEMS = [
    {
        "name": "Дуб Мудрости", "description": "Мощное дерево, символизирующее финансовую мудрость",
        "cost": 500, "currency": "xp", "color": "#4CAF50", "emoji": "🌳",
        "category": "trees", "is_new": False,
        "stages": [{"emoji": "🌱", "label": "Саженец"}, {"emoji": "🌿", "label": "Росток"}, {"emoji": "🌳", "label": "Дуб"}],
    },
    {
        "name": "Сакура Удачи", "description": "Цветущая сакура приносит финансовую удачу",
        "cost": 300, "currency": "xp", "color": "#FF80AB", "emoji": "🌸",
        "category": "trees", "is_new": True,
        "stages": [{"emoji": "🌱", "label": "Росток"}, {"emoji": "🌺", "label": "Бутон"}, {"emoji": "🌸", "label": "Цветение"}],
    },
    {
        "name": "Бамбук Роста", "description": "Быстрорастущий бамбук — символ постоянного роста",
        "cost": 200, "currency": "xp", "color": "#8BC34A", "emoji": "🎋",
        "category": "trees", "is_new": False,
        "stages": [{"emoji": "🌱", "label": "Побег"}, {"emoji": "🎍", "label": "Стебель"}, {"emoji": "🎋", "label": "Бамбук"}],
    },
    {
        "name": "Золотой горшок", "description": "Роскошный золотой горшок для вашего дерева",
        "cost": 50, "currency": "gem", "color": "#FFD700", "emoji": "🪴",
        "category": "decor", "is_new": False, "stages": [],
    },
    {
        "name": "Волшебный камень", "description": "Загадочный камень, притягивающий удачу",
        "cost": 30, "currency": "gem", "color": "#9C27B0", "emoji": "💎",
        "category": "decor", "is_new": False, "stages": [],
    },
    {
        "name": "Двойной XP", "description": "Удваивает получаемый XP на 24 часа",
        "cost": 100, "currency": "xp", "color": "#FF9800", "emoji": "⚡",
        "category": "boosts", "is_new": True, "stages": [],
    },
    {
        "name": "Защита серии", "description": "Сохраняет вашу серию активности на 1 день",
        "cost": 50, "currency": "gem", "color": "#2196F3", "emoji": "🛡️",
        "category": "boosts", "is_new": False, "stages": [],
    },
]

SEED_SKILLS = [
    {"label": "Накопления", "value": 3, "color": "primary"},
    {"label": "Инвестиции", "value": 1, "color": "warning"},
    {"label": "Планирование", "value": 5, "color": "primary"},
    {"label": "Контроль расходов", "value": 4, "color": "primary"},
    {"label": "Фин. грамотность", "value": 2, "color": "warning"},
]


def get_level_info(xp_total: int) -> dict:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp_total >= threshold:
            level = i + 1
    level = min(level, len(LEVEL_THRESHOLDS))
    xp_base = LEVEL_THRESHOLDS[level - 1]
    xp_next = LEVEL_THRESHOLDS[level] if level < len(LEVEL_THRESHOLDS) else LEVEL_THRESHOLDS[-1] + 1000
    return {
        "level": level,
        "label": LEVEL_LABELS[level - 1],
        "xp": xp_total - xp_base,
        "xpToNext": xp_next - xp_base,
        "xpTotal": xp_total,
    }


async def seed_static_data(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count()).select_from(Category))).scalar()
    if count and count > 0:
        return
    try:
        for cat in SEED_CATEGORIES:
            db.add(Category(**cat))
        for lesson_data in SEED_LESSONS:
            db.add(Lesson(**lesson_data))
        for ch_data in SEED_CHALLENGES:
            db.add(Challenge(**ch_data))
        for ach_data in SEED_ACHIEVEMENTS:
            db.add(Achievement(**ach_data))
        for item_data in SEED_MARKET_ITEMS:
            stages = item_data.pop("stages")
            db.add(MarketItem(**item_data, stages_json=json.dumps(stages, ensure_ascii=False)))
        await db.commit()
    except Exception:
        await db.rollback()


async def get_or_init_profile(user_uuid, db: AsyncSession) -> UserProfile:
    profile = await db.get(UserProfile, user_uuid)
    if profile is None:
        profile = UserProfile(user_uuid=user_uuid)
        db.add(profile)
        await db.flush()

    # Каждый блок идемпотентен: создаёт данные только если их ещё нет.
    # Это позволяет миграциям предзаполнять данные без конфликтов.

    skill_count = (await db.execute(
        select(func.count()).select_from(UserSkill).where(UserSkill.user_uuid == user_uuid)
    )).scalar()
    if not skill_count:
        for skill_data in SEED_SKILLS:
            db.add(UserSkill(user_uuid=user_uuid, **skill_data))

    history_count = (await db.execute(
        select(func.count()).select_from(XpHistory).where(XpHistory.user_uuid == user_uuid)
    )).scalar()
    if not history_count:
        now = datetime.utcnow()
        for i in range(5, -1, -1):
            month_idx = (now.month - i - 1) % 12
            db.add(XpHistory(user_uuid=user_uuid, month=MONTHS_RU[month_idx], value=0))

    lesson_count = (await db.execute(
        select(func.count()).select_from(UserLesson).where(UserLesson.user_uuid == user_uuid)
    )).scalar()
    if not lesson_count:
        lessons = (await db.execute(select(Lesson).order_by(Lesson.number))).scalars().all()
        for idx, lesson in enumerate(lessons):
            status = "in-progress" if idx == 0 else "locked"
            db.add(UserLesson(user_uuid=user_uuid, lesson_id=lesson.id, status=status))

    regular_challenge_count = (await db.execute(
        select(func.count()).select_from(UserChallenge)
        .join(Challenge, UserChallenge.challenge_id == Challenge.id)
        .where(
            and_(
                UserChallenge.user_uuid == user_uuid,
                Challenge.type.in_(["daily", "weekly"]),
            )
        )
    )).scalar()
    if not regular_challenge_count:
        challenges = (await db.execute(
            select(Challenge).where(Challenge.type.in_(["daily", "weekly"]))
        )).scalars().all()
        for challenge in challenges:
            db.add(UserChallenge(user_uuid=user_uuid, challenge_id=challenge.id))

    achievement_count = (await db.execute(
        select(func.count()).select_from(UserAchievement).where(UserAchievement.user_uuid == user_uuid)
    )).scalar()
    if not achievement_count:
        achievements = (await db.execute(select(Achievement))).scalars().all()
        for achievement in achievements:
            db.add(UserAchievement(user_uuid=user_uuid, achievement_id=achievement.id, unlocked=False))

    market_count = (await db.execute(
        select(func.count()).select_from(UserMarketItem).where(UserMarketItem.user_uuid == user_uuid)
    )).scalar()
    if not market_count:
        items = (await db.execute(select(MarketItem))).scalars().all()
        for item in items:
            db.add(UserMarketItem(user_uuid=user_uuid, item_id=item.id))

    await db.commit()
    return profile
