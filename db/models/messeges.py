from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, Mapped

from db.database import Base
from db.lib.mixins import TimeMixin
from db.lib.types import pk_id


class Message(Base, TimeMixin):
    __tablename__ = "messeges"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_uuid: Mapped[pk_id] = mapped_column(ForeignKey("bank_user.user_uuid",))
    text: Mapped[str]
    nickname: Mapped[str]
    ai_generated: Mapped[bool] = mapped_column(nullable=False)
    ended_conversession: Mapped[bool] = mapped_column(nullable=False)



