import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from chatbot.domain.message_scheme import MessageBase
from chatbot.sdk.messege_repo import MessageRepo
from chatbot.sdk.redis_client import RedisClient
from db.database import get_db
from db.models.users import User
from db.models.finance import Challenge, UserChallenge
from shared.config.settings import get_settings
from shared.jwt.jwt import decode_access_token, SUB

settings = get_settings()
redis_client = RedisClient()

# user_uuid → WebSocket (для прямой доставки пока соединение живо)
active_connections: Dict[str, WebSocket] = {}

# request_id → Future (для ожидания ответа AI в рамках одного запроса)
pending_responses: Dict[str, asyncio.Future] = {}

RESPONSE_TIMEOUT = 30


# ─── Consumer helpers ─────────────────────────────────────────────────────────

def _format_tasks_text(tasks: list) -> str:
    lines = [f"Я составил для тебя {len(tasks)} персональных задачи:\n"]
    for task in tasks:
        lines.append(f"📋 {task.get('name', 'Задача')}")
        lines.append(f"{task.get('payload', '')}")
        lines.append(f"🏆 Награда: {task.get('reward', 0)} XP\n")
    return "\n".join(lines)


async def _handle_ai_message(data: dict) -> None:
    """
    Обрабатывает обычный ответ AI (type='msg').
    Порядок: сначала пишем в БД, потом доставляем по WebSocket.
    Так сообщение не теряется даже при разрыве соединения.
    """
    user_uuid_str = data.get('user_uuid')
    text = data.get('message', '')
    request_id = data.get('request_id')

    if not user_uuid_str or not text:
        return

    try:
        msg = MessageBase(
            user_uuid=uuid.UUID(user_uuid_str),
            text=text,
            ended_conversession=data.get('is_final_question', 'false') == 'true',
            ai_generated=True,
            nickname="Навигатор Мечты",
        )

        # 1. Сохраняем в БД — всегда, независимо от состояния WebSocket
        async for db in get_db():
            await MessageRepo(db).add_message(msg)
            break

        msg_json = msg.model_dump_json()

        # 2. Если есть ожидающий future — резолвим его (WebSocket handler отправит)
        if request_id and request_id in pending_responses:
            fut = pending_responses.get(request_id)
            if fut and not fut.done():
                fut.set_result(msg_json)
            pending_responses.pop(request_id, None)
        else:
            # Future уже нет (таймаут или переподключение),
            # но WebSocket может быть открыт — шлём напрямую
            ws = active_connections.get(user_uuid_str)
            if ws:
                try:
                    await ws.send_text(msg_json)
                except Exception:
                    pass

    except Exception as e:
        print(f"[CONSUMER] Ошибка обработки сообщения: {e}")


async def _save_ai_tasks(data: dict) -> None:
    """Сохраняет задачи от AI в БД и доставляет форматированное сообщение в WebSocket."""
    user_uuid_str = data.get('user_uuid')
    tasks_raw = data.get('tasks', '[]')
    try:
        tasks = json.loads(tasks_raw)
    except (json.JSONDecodeError, TypeError):
        print("[TASKS] Не удалось распарсить tasks JSON")
        return

    if not user_uuid_str or not tasks:
        return

    try:
        user_uuid_obj = uuid.UUID(user_uuid_str)

        # Сохраняем задачи в БД
        async for db in get_db():
            for task in tasks:
                challenge = Challenge(
                    title=task.get('name', 'Задача от ИИ'),
                    description=task.get('payload', ''),
                    total=1,
                    reward=int(task.get('reward', 50)),
                    type='ai',
                )
                db.add(challenge)
                await db.flush()
                db.add(UserChallenge(
                    user_uuid=user_uuid_obj,
                    challenge_id=challenge.id,
                    progress=0,
                    status='pending',
                ))
            await db.commit()
            print(f"[TASKS] Создано {len(tasks)} задач для {user_uuid_str}")
            break

        # Форматируем и сохраняем сообщение о задачах в историю чата
        tasks_msg = MessageBase(
            user_uuid=user_uuid_obj,
            text=_format_tasks_text(tasks),
            ended_conversession=True,
            ai_generated=True,
            nickname="Навигатор Мечты",
        )
        async for db in get_db():
            await MessageRepo(db).add_message(tasks_msg)
            break

        # Доставляем в WebSocket если пользователь онлайн
        ws = active_connections.get(user_uuid_str)
        if ws:
            try:
                await ws.send_text(tasks_msg.model_dump_json())
            except Exception:
                pass

    except Exception as e:
        print(f"[TASKS] Ошибка: {e}")


# ─── Consumer loop ────────────────────────────────────────────────────────────

async def consume_responses() -> None:
    """
    Читает ответы AI из Redis Stream.

    Ключевые улучшения по сравнению с исходной версией:
    - XREAD BLOCK 2000: блокирующее чтение вместо polling + sleep(0.01)
      → меньше нагрузки, соединение не висит idle
    - asyncio.wait_for(timeout=10): если Redis не отвечает вообще — детектим
    - reconnect() при любой ошибке: пересоздаём клиент вместо продолжения
      с мёртвым соединением
    - Сначала пишем в БД, потом доставляем по WS: сообщения не теряются
    """
    last_id = '0'
    print("[CONSUMER] Запущен")

    while True:
        try:
            # Блокирующий XREAD на 2 секунды.
            # При отсутствии сообщений Redis возвращает пустой ответ через 2с.
            # asyncio.wait_for(10с) ловит полностью мёртвое соединение.
            messages = await asyncio.wait_for(
                redis_client.read_messages('response', last_id, count=10, block_ms=2000),
                timeout=10.0,
            )

        except asyncio.TimeoutError:
            # Redis не ответил за 10с — соединение мертво, переподключаемся
            print("[CONSUMER] Redis таймаут — переподключение...")
            await redis_client.reconnect()
            await asyncio.sleep(1)
            continue

        except asyncio.CancelledError:
            print("[CONSUMER] Остановлен")
            break

        except Exception as e:
            print(f"[CONSUMER] Ошибка Redis: {e} — переподключение...")
            await redis_client.reconnect()
            await asyncio.sleep(2)
            continue

        if not messages:
            # Нормальная ситуация: 2 секунды прошли, новых сообщений нет
            continue

        for msg_id, data in messages:
            last_id = msg_id
            msg_type = data.get('type', 'msg')
            print(f"[CONSUMER] msg_id={msg_id} type={msg_type}")

            try:
                if msg_type == 'tasks':
                    await _save_ai_tasks(data)
                else:
                    await _handle_ai_message(data)

                await redis_client.delete_message('response', msg_id)
            except Exception as e:
                print(f"[CONSUMER] Ошибка обработки {msg_id}: {e}")


# ─── App ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.create_consumer_group("request", "workers")
    task = asyncio.create_task(consume_responses())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await redis_client.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(o).rstrip("/") for o in settings.shared_settings.cors_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.shared_settings.allowed_hosts,
)


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/chatbot/ws")
async def websocket_handler(websocket: WebSocket, token: str | None = None):
    token_data = None
    user = None

    async for db in get_db():
        if token:
            token_data = await decode_access_token(token=token, db=db)
            user = await User.find_by_expr(db=db, expr=(User.user_uuid == token_data[SUB]))
        break

    if not token_data or not token_data.get(SUB):
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()

    user_uuid = str(token_data[SUB])
    active_connections[user_uuid] = websocket

    # Отправляем историю сразу после подключения
    async for db in get_db():
        messages = await MessageRepo(db).get_conversation(uuid.UUID(user_uuid))
        await websocket.send_text(json.dumps([m.model_dump_json() for m in messages]))
        break

    try:
        while True:
            try:
                user_msg = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                break

            request_id = str(uuid.uuid4())
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            pending_responses[request_id] = future

            # Сохраняем сообщение пользователя в БД сразу
            msg = MessageBase(
                user_uuid=uuid.UUID(user_uuid),
                text=user_msg,
                ended_conversession=False,
                ai_generated=False,
                nickname=f"{user.firstname} {user.lastname}" if user else "Пользователь",
            )
            async for db in get_db():
                await MessageRepo(db).add_message(msg)
                break

            # Кладём в очередь AI
            await redis_client.push_message("request", {
                'user_uuid': user_uuid,
                'request_id': request_id,
                'message': user_msg,
            })

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
    finally:
        active_connections.pop(user_uuid, None)
