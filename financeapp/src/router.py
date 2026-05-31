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
    Transaction, Category, UserProfile,
    Goal, Milestone, MilestoneSubtask, SavingsGoal,
)
from shared.dependencies import get_current_user
from shared.finance_seed import get_or_init_profile, MONTHS_RU

router = APIRouter(tags=["finance"])


# ─── Schemas ───────────────────────────────────────────────────────────────

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


# ─── Balance ───────────────────────────────────────────────────────────────

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


# ─── Transactions ──────────────────────────────────────────────────────────

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
    tx = Transaction(user_uuid=uid, title=body.title, amount=body.amount,
                     category=body.category, type=body.type, date=date)
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
    return {"id": str(t.id), "title": t.title, "amount": t.amount,
            "category": t.category, "type": t.type, "date": t.date.isoformat()}


# ─── Categories ────────────────────────────────────────────────────────────

@router.get("/categories/expense")
async def get_expense_categories(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Category).where(Category.type == "expense"))).scalars().all()
    return [{"id": c.id, "label": c.label, "emoji": c.emoji} for c in rows]


@router.get("/categories/income")
async def get_income_categories(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Category).where(Category.type == "income"))).scalars().all()
    return [{"id": c.id, "label": c.label, "emoji": c.emoji} for c in rows]


# ─── Goals ─────────────────────────────────────────────────────────────────

@router.get("/goals")
async def get_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goals = (await db.execute(select(Goal).where(Goal.user_uuid == current_user.user_uuid))).scalars().all()
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
    milestones = (await db.execute(select(Milestone).where(Milestone.goal_id == goal_id))).scalars().all()
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
    return {"id": str(g.id), "title": g.title, "current": g.current,
            "target": g.target, "deadline": g.deadline}


def _milestone_dict(m: Milestone, subtasks) -> dict:
    return {
        "id": str(m.id), "title": m.title, "description": m.description,
        "date": m.date, "xp": m.xp, "status": m.status,
        "subtasks": [{"id": str(s.id), "text": s.text, "done": s.done} for s in subtasks],
    }


# ─── Budget ────────────────────────────────────────────────────────────────

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
        "monthlyPlan": {"target": profile.monthly_limit, "projected": month_expenses},
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
    profile = await get_or_init_profile(current_user.user_uuid, db)
    profile.monthly_limit = body.monthlyLimit
    await db.commit()
    return {"monthlyLimit": profile.monthly_limit}


@router.get("/budget/goals")
async def get_savings_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    goals = (await db.execute(
        select(SavingsGoal).where(SavingsGoal.user_uuid == current_user.user_uuid)
    )).scalars().all()
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
    return {"id": str(g.id), "title": g.title, "description": g.description,
            "icon": g.icon, "current": g.current, "target": g.target}


# ─── Analytics ─────────────────────────────────────────────────────────────

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
        end = now if i == 0 else (start.replace(day=28) + timedelta(days=4)).replace(day=1)

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

        result.append({"month": MONTHS_RU[start.month - 1], "income": income, "expense": expense})
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
        c.id: c for c in (await db.execute(
            select(Category).where(Category.type == "expense")
        )).scalars().all()
    }
    return [
        {
            "label": categories[r.category].label if r.category in categories else r.category,
            "value": r.total,
            "color": categories[r.category].color if r.category in categories else "#90A4AE",
        }
        for r in rows
    ]
