import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict

import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from chatbot.domain.message_scheme import MessageBase
from chatbot.sdk.messege_repo import MessageRepo
from chatbot.sdk.redis_client import RedisClient
from db.database import get_db
from db.models.users import User
from shared.config.settings import get_settings
from shared.jwt.jwt import decode_access_token, SUB

settings = get_settings()
redis_client = RedisClient()
pending_responses: Dict[str, asyncio.Future] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_client.create_consumer_group("requests", "workers")
    task = asyncio.create_task(consume_responses())

    yield

    task.cancel()
    await task
    await redis_client.close()


app = FastAPI(lifespan=lifespan, )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.shared_settings.cors_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.shared_settings.allowed_hosts
)


async def consume_responses():
    """Фоновая задача: читает ответы и отдаёт ожидающим запросам"""
    last_id = '0'
    print("Фоновая задача: читает ответы и отдаёт ожидающим запросам")
    while True:
        messages = await redis_client.read_messages('requests', last_id, count=10)
        print(f"Мы получили объект {messages}")
        if messages:
            for msg_id, data in messages:
                last_id = msg_id
                request_id = data.get('user_uuid')

                if request_id and request_id in pending_responses:
                    response = data.get('response', data.get('message'))
                    pending_responses[request_id].set_result(response)
                    del pending_responses[request_id]

                    await redis_client.delete_message('requests', msg_id)

        await asyncio.sleep(0.01)


async def handle_websocket(websocket: WebSocket, token_data, user):
    user_uuid = str(token_data.get(SUB))

    try:
        user_msg = await websocket.receive_text()
    except WebSocketDisconnect:
        # Клиент отвалился до отправки — выходим
        return

    future = asyncio.Future()
    pending_responses[user_uuid] = future

    msg = MessageBase(
        user_uuid=user_uuid,
        text=user_msg,
        ended_conversession=False,
        ai_generated=True,
        nickname=str(user.firstname) + " " + str(user.lastname),
    )

    await redis_client.push_message("requests", {
        'user_uuid': user_uuid,
        'message': msg.model_dump_json()
    })

    async for db in get_db():
        await MessageRepo(db).add_message(msg)
        break

    try:
        response = await future
        await websocket.send_text(response)
    except WebSocketDisconnect:
        pass
    finally:
        pending_responses.pop(user_uuid, None)

@app.websocket("/chatbot/ws")
async def websocket_handler(websocket: WebSocket, token: str | None = None):
    token_data = None
    user = None
    async for db in get_db():
        if token:
            token_data = await decode_access_token(token=token, db=db)
            expr = (User.user_uuid == token_data[SUB])
            user: User = await User.find_by_expr(db=db, expr=expr)

    if not token_data or not token_data.get(SUB):
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()


    try:
        async for db in get_db():
            messages = await MessageRepo(db).get_conversation(token_data[SUB])
            messages_json = json.dumps([msg.model_dump_json() for msg in messages])
            await websocket.send_text(messages_json)

            break

        while True:
            await handle_websocket(websocket, token_data, user)

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
