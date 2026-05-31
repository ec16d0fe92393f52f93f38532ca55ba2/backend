import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from authapp.src.routers import router as router_auth

from fastapi import Response

from shared.config.settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)


# @app.middleware("http")
# async def add_cors_headers(request, call_next):
#     response = Response()
#
#     if request.method == "OPTIONS":
#         response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
#         response.headers["Access-Control-Allow-Credentials"] = "true"
#         response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
#         response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
#         return response
#
#     response = await call_next(request)
#
#     response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
#     response.headers["Access-Control-Allow-Credentials"] = "true"
#     response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
#     response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
#
#     return response

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
    allowed_hosts= settings.shared_settings.allowed_hosts
)


app.include_router(router_auth)




if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
    #для запуска через консоль с перезагрузкой сервера на том же порту и хосте: uvicorn run_web:app --reload --host 0.0.0.0 --port 8000