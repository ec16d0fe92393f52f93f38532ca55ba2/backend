import uuid
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.database import Base
from db.lib.types import pk_id


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    emoji: Mapped[str] = mapped_column(String(10))
    type: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(20), nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(20))
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    gems: Mapped[int] = mapped_column(Integer, default=100)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    growth_points: Mapped[int] = mapped_column(Integer, default=0)
    financial_score: Mapped[int] = mapped_column(Integer, default=50)
    monthly_limit: Mapped[float] = mapped_column(Float, default=0.0)
    tree_leaves: Mapped[int] = mapped_column(Integer, default=0)
    leaves_to_next: Mapped[int] = mapped_column(Integer, default=10)


class XpHistory(Base):
    __tablename__ = "xp_history"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    month: Mapped[str] = mapped_column(String(20))
    value: Mapped[int] = mapped_column(Integer, default=0)


class UserSkill(Base):
    __tablename__ = "user_skills"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    value: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(20), default="primary")


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    current: Mapped[float] = mapped_column(Float, default=0.0)
    target: Mapped[float] = mapped_column(Float)
    deadline: Mapped[str] = mapped_column(String(30))


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[pk_id]
    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goals.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[str] = mapped_column(String(30))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="locked")


class MilestoneSubtask(Base):
    __tablename__ = "milestone_subtasks"
    id: Mapped[pk_id]
    milestone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("milestones.id"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[pk_id]
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    subtitle: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    xp: Mapped[int] = mapped_column(Integer, default=50)
    duration: Mapped[int] = mapped_column(Integer, default=10)


class UserLesson(Base):
    __tablename__ = "user_lessons"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id"))
    status: Mapped[str] = mapped_column(String(20), default="locked")
    progress: Mapped[int] = mapped_column(Integer, default=0)


class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[pk_id]
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    total: Mapped[int] = mapped_column(Integer, default=1)
    reward: Mapped[int] = mapped_column(Integer, default=20)
    type: Mapped[str] = mapped_column(String(20))


class UserChallenge(Base):
    __tablename__ = "user_challenges"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id"))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[pk_id]
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    achievement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("achievements.id"))
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)


class MarketItem(Base):
    __tablename__ = "market_items"
    id: Mapped[pk_id]
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    cost: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10))
    color: Mapped[str] = mapped_column(String(30), default="#4CAF50")
    emoji: Mapped[str] = mapped_column(String(10), default="🌳")
    category: Mapped[str] = mapped_column(String(30))
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    stages_json: Mapped[str] = mapped_column(Text, default="[]")


class UserMarketItem(Base):
    __tablename__ = "user_market_items"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("market_items.id"))
    owned: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class SavingsGoal(Base):
    __tablename__ = "savings_goals"
    id: Mapped[pk_id]
    user_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_user.user_uuid"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(500), default="")
    icon: Mapped[str] = mapped_column(String(10), default="💰")
    current: Mapped[float] = mapped_column(Float, default=0.0)
    target: Mapped[float] = mapped_column(Float)
