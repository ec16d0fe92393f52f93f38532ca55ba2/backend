import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models.users import User
from db.models.finance import (
    Transaction, Category,
    Goal, Milestone, MilestoneSubtask, SavingsGoal,
)
from shared.dependencies import get_current_user
from shared.finance_seed import get_or_init_profile, MONTHS_RU
from financeapp.src.schemas import (
    BalanceResponse,
    TransactionCreate, TransactionResponse,
    CategoryResponse,
    GoalCreate, GoalUpdate, GoalResponse,
    MilestoneUpdate, MilestoneResponse, SubtaskUpdate, SubtaskResponse,
    SavingsGoalCreate, SavingsGoalResponse,
    BudgetLimitUpdate, BudgetLimitResponse, BudgetResponse, MonthlyPlanSchema,
    MonthlyAnalyticsItem, CategoryExpenseItem,
    OkResponse,
)

router = APIRouter(tags=["finance"])


# ─── Balance ─────────────────────────────────────────────────────────────────

@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> BalanceResponse:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)

    income: float = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "income"))
    )).scalar()

    expenses: float = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense"))
    )).scalar()

    saved: float = (await db.execute(
        select(func.coalesce(func.sum(SavingsGoal.current), 0))
        .where(SavingsGoal.user_uuid == uid)
    )).scalar()

    return BalanceResponse(total=income - expenses, income=income, expenses=expenses, saved=saved)


# ─── Transactions ────────────────────────────────────────────────────────────

@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    type: Optional[Literal['income', 'expense']] = None,
    limit: Optional[int] = None,
    date: Optional[str] = None,
) -> list[TransactionResponse]:
    uid = current_user.user_uuid
    q = select(Transaction).where(Transaction.user_uuid == uid).order_by(Transaction.date.desc())
    if type:
        q = q.where(Transaction.type == type)
    if date:
        try:
            day = datetime.fromisoformat(date).date()
            q = q.where(func.date(Transaction.date) == day)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date format, expected ISO 8601")
    if limit:
        q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [TransactionResponse.model_validate(t) for t in rows]


@router.post("/transactions", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    uid = current_user.user_uuid
    await get_or_init_profile(uid, db)
    tx = Transaction(
        user_uuid=uid,
        title=body.title,
        amount=body.amount,
        category=body.category,
        type=body.type,
        date=body.date or datetime.utcnow(),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return TransactionResponse.model_validate(tx)


@router.delete("/transactions/{tx_id}", response_model=OkResponse)
async def delete_transaction(
    tx_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    tx = await db.get(Transaction, tx_id)
    if not tx or tx.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.delete(tx)
    await db.commit()
    return OkResponse(ok=True)


# ─── Categories ──────────────────────────────────────────────────────────────

@router.get("/categories/expense", response_model=list[CategoryResponse])
async def get_expense_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryResponse]:
    rows = (await db.execute(select(Category).where(Category.type == "expense"))).scalars().all()
    return [CategoryResponse.model_validate(c) for c in rows]


@router.get("/categories/income", response_model=list[CategoryResponse])
async def get_income_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryResponse]:
    rows = (await db.execute(select(Category).where(Category.type == "income"))).scalars().all()
    return [CategoryResponse.model_validate(c) for c in rows]


# ─── Goals ───────────────────────────────────────────────────────────────────

@router.get("/goals", response_model=list[GoalResponse])
async def get_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[GoalResponse]:
    goals = (await db.execute(
        select(Goal).where(Goal.user_uuid == current_user.user_uuid)
    )).scalars().all()
    return [GoalResponse(id=g.id, title=g.title, current=g.current,
                         target=g.target, deadline=g.deadline) for g in goals]


@router.post("/goals", response_model=GoalResponse, status_code=201)
async def create_goal(
    body: GoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    goal = Goal(
        user_uuid=current_user.user_uuid,
        title=body.title,
        target=body.target,
        deadline=body.deadline.isoformat(),
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return GoalResponse(id=goal.id, title=goal.title, current=goal.current,
                        target=goal.target, deadline=goal.deadline)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    goal = await db.get(Goal, goal_id)
    if not goal or goal.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Goal not found")

    update_data = body.model_dump(exclude_none=True)
    if 'deadline' in update_data:
        update_data['deadline'] = update_data['deadline'].isoformat()
    for field, val in update_data.items():
        setattr(goal, field, val)

    await db.commit()
    await db.refresh(goal)
    return GoalResponse(id=goal.id, title=goal.title, current=goal.current,
                        target=goal.target, deadline=goal.deadline)


@router.get("/goals/{goal_id}/milestones", response_model=list[MilestoneResponse])
async def get_milestones(
    goal_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[MilestoneResponse]:
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
        result.append(_build_milestone_response(m, subtasks))
    return result


@router.patch("/goals/{goal_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MilestoneResponse:
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
    return _build_milestone_response(milestone, subtasks)


@router.patch(
    "/goals/{goal_id}/milestones/{milestone_id}/subtasks/{subtask_id}",
    response_model=SubtaskResponse,
)
async def toggle_subtask(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    subtask_id: uuid.UUID,
    body: SubtaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SubtaskResponse:
    goal = await db.get(Goal, goal_id)
    if not goal or goal.user_uuid != current_user.user_uuid:
        raise HTTPException(status_code=404, detail="Goal not found")
    subtask = await db.get(MilestoneSubtask, subtask_id)
    if not subtask or subtask.milestone_id != milestone_id:
        raise HTTPException(status_code=404, detail="Subtask not found")
    subtask.done = body.done
    await db.commit()
    return SubtaskResponse(id=subtask.id, text=subtask.text, done=subtask.done)


def _build_milestone_response(m: Milestone, subtasks) -> MilestoneResponse:
    return MilestoneResponse(
        id=m.id,
        title=m.title,
        description=m.description,
        date=m.date,
        xp=m.xp,
        status=m.status,
        subtasks=[SubtaskResponse(id=s.id, text=s.text, done=s.done) for s in subtasks],
    )


# ─── Budget ──────────────────────────────────────────────────────────────────

@router.get("/budget", response_model=BudgetResponse)
async def get_budget(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> BudgetResponse:
    uid = current_user.user_uuid
    profile = await get_or_init_profile(uid, db)

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_expenses: float = (await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense",
                    Transaction.date >= month_start))
    )).scalar()

    savings_goals = (await db.execute(
        select(SavingsGoal).where(SavingsGoal.user_uuid == uid)
    )).scalars().all()

    return BudgetResponse(
        monthlyLimit=profile.monthly_limit,
        monthlyPlan=MonthlyPlanSchema(target=profile.monthly_limit, projected=month_expenses),
        goals=[SavingsGoalResponse.model_validate(g) for g in savings_goals],
        treeLeaves=profile.tree_leaves,
        leavesToNext=profile.leaves_to_next,
    )


@router.patch("/budget/limit", response_model=BudgetLimitResponse)
async def update_budget_limit(
    body: BudgetLimitUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> BudgetLimitResponse:
    profile = await get_or_init_profile(current_user.user_uuid, db)
    profile.monthly_limit = body.monthlyLimit
    await db.commit()
    return BudgetLimitResponse(monthlyLimit=profile.monthly_limit)


@router.get("/budget/goals", response_model=list[SavingsGoalResponse])
async def get_savings_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[SavingsGoalResponse]:
    goals = (await db.execute(
        select(SavingsGoal).where(SavingsGoal.user_uuid == current_user.user_uuid)
    )).scalars().all()
    return [SavingsGoalResponse.model_validate(g) for g in goals]


@router.post("/budget/goals", response_model=SavingsGoalResponse, status_code=201)
async def create_savings_goal(
    body: SavingsGoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SavingsGoalResponse:
    goal = SavingsGoal(user_uuid=current_user.user_uuid, **body.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return SavingsGoalResponse.model_validate(goal)


# ─── Analytics ───────────────────────────────────────────────────────────────

@router.get("/analytics/monthly", response_model=list[MonthlyAnalyticsItem])
async def get_monthly_analytics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    months: int = 6,
) -> list[MonthlyAnalyticsItem]:
    uid = current_user.user_uuid
    now = datetime.utcnow()
    result = []
    for i in range(months - 1, -1, -1):
        start = (now.replace(day=1) - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = now if i == 0 else (start.replace(day=28) + timedelta(days=4)).replace(day=1)

        income: float = (await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(and_(Transaction.user_uuid == uid, Transaction.type == "income",
                        Transaction.date >= start, Transaction.date < end))
        )).scalar()

        expense: float = (await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(and_(Transaction.user_uuid == uid, Transaction.type == "expense",
                        Transaction.date >= start, Transaction.date < end))
        )).scalar()

        result.append(MonthlyAnalyticsItem(month=MONTHS_RU[start.month - 1], income=income, expense=expense))
    return result


@router.get("/analytics/expenses/by-category", response_model=list[CategoryExpenseItem])
async def get_expenses_by_category(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[CategoryExpenseItem]:
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
        CategoryExpenseItem(
            label=categories[r.category].label if r.category in categories else r.category,
            value=r.total,
            color=categories[r.category].color if r.category in categories else "#90A4AE",
        )
        for r in rows
    ]
