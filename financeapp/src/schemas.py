import uuid
from datetime import datetime, date, timezone
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, field_validator


# ─── Shared ──────────────────────────────────────────────────────────────────

class OkResponse(BaseModel):
    ok: bool


# ─── Transaction ─────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    title: str
    amount: float
    category: str
    type: Literal['income', 'expense']
    date: Optional[datetime] = None

    @field_validator('date', mode='after')
    @classmethod
    def strip_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Приводим к UTC и снимаем tzinfo — БД хранит TIMESTAMP WITHOUT TIME ZONE."""
        if v is not None and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    amount: float
    category: str
    type: Literal['income', 'expense']
    date: datetime


# ─── Balance ─────────────────────────────────────────────────────────────────

class BalanceResponse(BaseModel):
    total: float
    income: float
    expenses: float
    saved: float


# ─── Category ────────────────────────────────────────────────────────────────

class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    emoji: str


# ─── Goals ───────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    target: float
    deadline: date

    @field_validator('deadline', mode='before')
    @classmethod
    def parse_deadline(cls, v):
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    current: Optional[float] = None
    target: Optional[float] = None
    deadline: Optional[date] = None

    @field_validator('deadline', mode='before')
    @classmethod
    def parse_deadline(cls, v):
        if v is None or isinstance(v, date):
            return v
        return date.fromisoformat(v)


class GoalResponse(BaseModel):
    id: uuid.UUID
    title: str
    current: float
    target: float
    deadline: str  # ISO date string — хранится как строка в БД


# ─── Milestones ──────────────────────────────────────────────────────────────

class SubtaskResponse(BaseModel):
    id: uuid.UUID
    text: str
    done: bool


class SubtaskUpdate(BaseModel):
    done: bool


class MilestoneUpdate(BaseModel):
    status: Optional[Literal['completed', 'current', 'locked']] = None
    title: Optional[str] = None


class MilestoneResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    date: str  # ISO date string
    xp: int
    status: Literal['completed', 'current', 'locked']
    subtasks: list[SubtaskResponse]


# ─── Savings Goals ───────────────────────────────────────────────────────────

class SavingsGoalCreate(BaseModel):
    title: str
    description: str = ""
    icon: str = "💰"
    target: float


class SavingsGoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    icon: str
    current: float
    target: float


# ─── Budget ──────────────────────────────────────────────────────────────────

class BudgetLimitUpdate(BaseModel):
    monthlyLimit: float


class BudgetLimitResponse(BaseModel):
    monthlyLimit: float


class MonthlyPlanSchema(BaseModel):
    target: float
    projected: float


class BudgetResponse(BaseModel):
    monthlyLimit: float
    monthlyPlan: MonthlyPlanSchema
    goals: list[SavingsGoalResponse]
    treeLeaves: int
    leavesToNext: int


# ─── Analytics ───────────────────────────────────────────────────────────────

class MonthlyAnalyticsItem(BaseModel):
    month: str
    income: float
    expense: float


class CategoryExpenseItem(BaseModel):
    label: str
    value: float
    color: str
