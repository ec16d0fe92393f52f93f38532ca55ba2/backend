import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chatbot.domain.message_scheme import MessageItem, MessageBase
from db.models.messeges import Message


class MessageRepo:

    def __init__(self, session: AsyncSession):
        self.session = session


    async def add_message(self, message_base: MessageBase):

        model = Message(
            text=message_base.text,
            nickname=message_base.nickname,
            user_uuid=message_base.user_uuid,
            ai_generated=message_base.ai_generated,
            ended_conversession=message_base.ended_conversession
        )

        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)

        return MessageItem.model_validate(model)

    async def get_conversation(self, user_uuid: uuid.UUID, limit = 100) -> List[MessageItem]:

        query = select(Message).where(Message.user_uuid == user_uuid).limit(limit)

        result = await self.session.execute(query)

        scalars = result.scalars().all()
        msg_list = [ MessageItem.model_validate(scalar) for scalar in scalars ]

        return msg_list


