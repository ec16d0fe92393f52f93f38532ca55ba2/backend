import asyncio
import json
import uuid
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

RESPONSE_TIMEOUT = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.create_consumer_group("requests", "workers")
    mock_task = asyncio.create_task(mock_worker())
    consume_task = asyncio.create_task(consume_responses())

    yield

    mock_task.cancel()
    consume_task.cancel()
    await asyncio.gather(mock_task, consume_task, return_exceptions=True)
    await redis_client.close()


app = FastAPI(lifespan=lifespan)

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


async def mock_worker():
    print("[MOCK] Запущен mock-воркер")
    last_id = '0'
    while True:
        try:
            messages = await redis_client.read_messages('requests', last_id, count=10)
        except Exception as e:
            print(f"[MOCK] Ошибка чтения: {e}")
            await asyncio.sleep(1)
            continue

        if messages:
            for msg_id, data in messages:
                last_id = msg_id
                print(f"[MOCK] Получен запрос: {data}")

                request_id = data.get('request_id')
                user_uuid = data.get('user_uuid')

                if not request_id:
                    continue

                await asyncio.sleep(2)

                response_data = {
                    'user_uuid': user_uuid,
                    'request_id': request_id,
                    'response': f'Ответ на: {data.get("message", "")}'
                }

                print(f"[MOCK] Отправляю ответ: {response_data}")
                await redis_client.push_message('responses', response_data)
                await redis_client.delete_message('requests', msg_id)

        await asyncio.sleep(0.1)


async def consume_responses():
    last_id = '0'
    print("[CONSUME] Запущена consume_responses")
    while True:
        try:
            messages = await redis_client.read_messages('responses', last_id, count=10)
        except Exception as e:
            print(f"[CONSUME] Ошибка: {e}")
            await asyncio.sleep(1)
            continue

        if messages:
            for msg_id, data in messages:
                last_id = msg_id
                request_id = data.get('request_id')
                print(f"[CONSUME] Получен ответ для {request_id}")

                if request_id and request_id in pending_responses:
                    response = data.get('response', '')
                    try:
                        if not pending_responses[request_id].done():
                            pending_responses[request_id].set_result(response)
                            print(f"[CONSUME] Ответ доставлен для {request_id}")
                    except asyncio.InvalidStateError:
                        print(f"[CONSUME] Future для {request_id} уже завершён")
                    pending_responses.pop(request_id, None)
                    await redis_client.delete_message('responses', msg_id)

        await asyncio.sleep(0.01)


@app.websocket("/chatbot/ws")
async def websocket_handler(websocket: WebSocket, token: str | None = None):
    token_data = None
    user = None
    async for db in get_db():
        if token:
            token_data = await decode_access_token(token=token, db=db)
            expr = (User.user_uuid == token_data[SUB])
            user = await User.find_by_expr(db=db, expr=expr)

    if not token_data or not token_data.get(SUB):
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()

    user_uuid = str(token_data[SUB])

    async for db in get_db():
        messages = await MessageRepo(db).get_conversation(user_uuid)
        messages_json = json.dumps([msg.model_dump_json() for msg in messages])
        await websocket.send_text(messages_json)
        break

    try:
        while True:
            try:
                user_msg = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                break

            request_id = str(uuid.uuid4())
            future = asyncio.Future()
            pending_responses[request_id] = future

            msg = MessageBase(
                user_uuid=user_uuid,
                text=user_msg,
                ended_conversession=False,
                ai_generated=False,
                nickname=str(user.firstname) + " " + str(user.lastname),
            )

            await redis_client.push_message("requests", {
                'user_uuid': user_uuid,
                'request_id': request_id,
                'message': msg.model_dump_json()
            })

            async for db in get_db():
                await MessageRepo(db).add_message(msg)
                break

            try:
                response = await asyncio.wait_for(future, timeout=RESPONSE_TIMEOUT)
                await websocket.send_text(response)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"error": "timeout"}))
            except (WebSocketDisconnect, RuntimeError):
                break
            finally:
                pending_responses.pop(request_id, None)

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)