"""demo user

Revision ID: d9e1f2a3b4c5
Revises: f7a3d21bc849
Create Date: 2026-05-31 07:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = 'd9e1f2a3b4c5'
down_revision: Union[str, None] = 'f7a3d21bc849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# demo@demo.com / demo123
_USER  = 'a1b2c3d4-e5f6-4890-abcd-ef1234567890'
_GOAL  = 'b2c3d4e5-f6a7-4901-bcde-f12345678901'
_M1    = 'c3d4e5f6-a7b8-4012-8def-123456789012'
_M2    = 'd4e5f6a7-b8c9-4123-9ef0-234567890123'
_M3    = 'e5f6a7b8-c9d0-4234-aef0-345678901234'
_SG1   = 'f6a7b8c9-d0e1-4345-bef0-456789012345'
_SG2   = 'a7b8c9d0-e1f2-4456-8ef0-567890123456'
_HASH  = '$2b$12$z9W2eGfLWIR.MBxZVN5ZyuALx8mkaqg.Mu9y5sbX1AlAx4qI5IRu.'


def upgrade() -> None:
    conn = op.get_bind()

    # Идемпотентно — не дублируем если уже есть
    exists = conn.execute(
        text("SELECT 1 FROM bank_user WHERE user_uuid = :uid"),
        {"uid": _USER},
    ).fetchone()
    if exists:
        return

    # ── Пользователь ─────────────────────────────────────────────────────────
    conn.execute(text("""
        INSERT INTO bank_user
            (user_uuid, email, phone, firstname, middlename, lastname, password, is_active)
        VALUES
            (:uid, 'demo@demo.com', '+79001234567',
             'Алексей', 'Иванович', 'Смирнов', :pwd, true)
    """), {"uid": _USER, "pwd": _HASH})

    # ── Профиль (XP 250 = уровень 2 «Росток») ────────────────────────────────
    conn.execute(text("""
        INSERT INTO user_profiles
            (user_uuid, xp, xp_total, gems, streak_days, last_activity_date,
             growth_points, financial_score, monthly_limit, tree_leaves, leaves_to_next)
        VALUES
            (:uid, 250, 250, 150, 7, '2026-05-31', 15, 72, 50000.0, 5, 5)
    """), {"uid": _USER})

    # ── Навыки (реалистичные значения) ───────────────────────────────────────
    skills = [
        ("Накопления",        6, "primary"),
        ("Инвестиции",        2, "warning"),
        ("Планирование",      7, "primary"),
        ("Контроль расходов", 5, "primary"),
        ("Фин. грамотность",  4, "warning"),
    ]
    for label, value, color in skills:
        conn.execute(text("""
            INSERT INTO user_skills (id, user_uuid, label, value, color)
            VALUES (gen_random_uuid(), :uid, :label, :value, :color)
        """), {"uid": _USER, "label": label, "value": value, "color": color})

    # ── История XP (последние 6 месяцев, нарастающая) ────────────────────────
    xp_history = [
        ("Дек", 0),
        ("Янв", 30),
        ("Фев", 50),
        ("Мар", 80),
        ("Апр", 120),
        ("Май", 250),
    ]
    for month, value in xp_history:
        conn.execute(text("""
            INSERT INTO xp_history (id, user_uuid, month, value)
            VALUES (gen_random_uuid(), :uid, :month, :value)
        """), {"uid": _USER, "month": month, "value": value})

    # ── Транзакции — апрель 2026 ─────────────────────────────────────────────
    april_txs = [
        ("Зарплата",    85000.0, "salary",        "income",  "2026-04-05 09:00:00"),
        ("Фриланс",     10000.0, "freelance",      "income",  "2026-04-20 15:00:00"),
        ("Продукты",     7500.0, "food",           "expense", "2026-04-07 19:00:00"),
        ("Метро",        2200.0, "transport",      "expense", "2026-04-09 08:30:00"),
        ("ЖКХ",          6800.0, "utilities",      "expense", "2026-04-15 12:00:00"),
        ("Кинотеатр",    4500.0, "entertainment",  "expense", "2026-04-22 20:00:00"),
        ("Куртка",       3800.0, "clothes",        "expense", "2026-04-25 14:00:00"),
    ]
    # ── Транзакции — май 2026 ────────────────────────────────────────────────
    may_txs = [
        ("Зарплата",    85000.0, "salary",        "income",  "2026-05-05 09:00:00"),
        ("Фриланс",     15000.0, "freelance",      "income",  "2026-05-15 17:00:00"),
        ("Продукты",     8200.0, "food",           "expense", "2026-05-06 19:30:00"),
        ("Кофе",          450.0, "food",           "expense", "2026-05-08 08:15:00"),
        ("Такси",        2500.0, "transport",      "expense", "2026-05-10 22:00:00"),
        ("ЖКХ",          6800.0, "utilities",      "expense", "2026-05-15 12:00:00"),
        ("Врач",         3200.0, "health",         "expense", "2026-05-18 11:00:00"),
        ("Концерт",      5500.0, "entertainment",  "expense", "2026-05-23 19:00:00"),
        ("Кроссовки",    4100.0, "clothes",        "expense", "2026-05-27 13:00:00"),
    ]
    for title, amount, category, tx_type, date_str in april_txs + may_txs:
        conn.execute(text("""
            INSERT INTO transactions (id, user_uuid, title, amount, category, type, date)
            VALUES (gen_random_uuid(), :uid, :title, :amount, :category, :type, :dt)
        """), {"uid": _USER, "title": title, "amount": amount, "category": category,
               "type": tx_type, "dt": datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")})

    # ── Финансовая цель ───────────────────────────────────────────────────────
    conn.execute(text("""
        INSERT INTO goals (id, user_uuid, title, current, target, deadline)
        VALUES (:gid, :uid, 'Накопить на отпуск в Японии', 65000.0, 200000.0, '2026-12-31')
    """), {"gid": _GOAL, "uid": _USER})

    # ── Вехи цели ─────────────────────────────────────────────────────────────
    milestones = [
        (_M1, "Открыть накопительный счёт",
              "Выбрать банк с максимальной ставкой и оформить счёт",
              "2026-02-01", 50, "completed"),
        (_M2, "Накопить первые 50 000 ₽",
              "Отложить первый значимый взнос в копилку",
              "2026-04-15", 75, "completed"),
        (_M3, "Достичь половины цели — 100 000 ₽",
              "Довести накопления до 100 000 ₽",
              "2026-08-01", 100, "current"),
    ]
    for mid, title, desc, date, xp, status in milestones:
        conn.execute(text("""
            INSERT INTO milestones (id, goal_id, title, description, date, xp, status)
            VALUES (:mid, :gid, :title, :desc, :date, :xp, :status)
        """), {"mid": mid, "gid": _GOAL, "title": title,
               "desc": desc, "date": date, "xp": xp, "status": status})

    # ── Подзадачи для текущей вехи ────────────────────────────────────────────
    subtasks = [
        ("Настроить автоперевод 30% зарплаты", True),
        ("Сократить расходы на развлечения до 5 000 ₽/мес", True),
        ("Найти дополнительный источник дохода", False),
        ("Пересмотреть подписки и отказаться от лишних", False),
    ]
    for text_val, done in subtasks:
        conn.execute(text("""
            INSERT INTO milestone_subtasks (id, milestone_id, text, done)
            VALUES (gen_random_uuid(), :mid, :text, :done)
        """), {"mid": _M3, "text": text_val, "done": done})

    # ── Цели накопления ───────────────────────────────────────────────────────
    conn.execute(text("""
        INSERT INTO savings_goals (id, user_uuid, title, description, icon, current, target)
        VALUES (:sid, :uid, 'Отпуск в Японии', 'Главная мечта года', '✈️', 65000.0, 200000.0)
    """), {"sid": _SG1, "uid": _USER})

    conn.execute(text("""
        INSERT INTO savings_goals (id, user_uuid, title, description, icon, current, target)
        VALUES (:sid, :uid, 'Новый ноутбук', 'MacBook Pro для работы', '💻', 20000.0, 80000.0)
    """), {"sid": _SG2, "uid": _USER})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DELETE FROM milestone_subtasks WHERE milestone_id IN (:m1, :m2, :m3)"),
                 {"m1": _M1, "m2": _M2, "m3": _M3})
    conn.execute(text("DELETE FROM milestones WHERE goal_id = :gid"), {"gid": _GOAL})
    conn.execute(text("DELETE FROM goals WHERE id = :gid"), {"gid": _GOAL})
    conn.execute(text("DELETE FROM savings_goals WHERE user_uuid = :uid"), {"uid": _USER})
    conn.execute(text("DELETE FROM transactions WHERE user_uuid = :uid"), {"uid": _USER})
    conn.execute(text("DELETE FROM xp_history WHERE user_uuid = :uid"), {"uid": _USER})
    conn.execute(text("DELETE FROM user_skills WHERE user_uuid = :uid"), {"uid": _USER})
    conn.execute(text("DELETE FROM user_profiles WHERE user_uuid = :uid"), {"uid": _USER})
    conn.execute(text("DELETE FROM bank_user WHERE user_uuid = :uid"), {"uid": _USER})
