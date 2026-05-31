import uuid
from typing import Literal, Optional
from pydantic import BaseModel


# ─── Tree / Level ────────────────────────────────────────────────────────────

class TreeLevelResponse(BaseModel):
    level: int
    label: str
    xp: int
    xpToNext: int
    xpTotal: int
    growthPoints: int
    financialScore: int


# ─── Skills ──────────────────────────────────────────────────────────────────

class SkillResponse(BaseModel):
    label: str
    value: int
    color: Literal['primary', 'warning']


# ─── XP History ──────────────────────────────────────────────────────────────

class XpHistoryItem(BaseModel):
    month: str
    value: int


# ─── Streak & Currency ───────────────────────────────────────────────────────

class StreakResponse(BaseModel):
    streakDays: int
    resetHours: int
    resetMinutes: int


class CurrencyResponse(BaseModel):
    xp: int
    gems: int


# ─── Lessons ─────────────────────────────────────────────────────────────────

class LessonResponse(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    subtitle: str
    description: str
    xp: int
    duration: int
    status: Literal['completed', 'in-progress', 'locked']
    progress: Optional[int] = None  # только для in-progress


class LessonCompleteResponse(BaseModel):
    ok: bool
    xpEarned: int


# ─── Challenges ──────────────────────────────────────────────────────────────

class ChallengeResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    progress: int
    total: int
    reward: int
    status: Literal['completed', 'pending']


class ChallengeCompleteResponse(BaseModel):
    ok: bool
    xpEarned: int


# ─── Achievements ────────────────────────────────────────────────────────────

class AchievementResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    unlocked: bool


# ─── Market ──────────────────────────────────────────────────────────────────

class GrowthStage(BaseModel):
    emoji: str
    label: str


class MarketItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    cost: int
    currency: Literal['xp', 'gem']
    owned: bool
    active: bool
    color: str
    emoji: str
    category: Literal['trees', 'decor', 'boosts']
    isNew: bool
    stages: list[GrowthStage]
