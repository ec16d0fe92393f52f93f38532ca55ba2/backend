
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir alembic sqlalchemy[asyncio] asyncpg python-dotenv passlib python-jose pydantic pydantic-settings


COPY ./db ./db
COPY ./shared ./shared
COPY ./alembic.ini ./alembic.ini
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD
ARG POSTGRES_HOST
ARG POSTGRES_PORT
ARG POSTGRES_NAME

ENV POSTGRES_USER=$POSTGRES_USER
ENV POSTGRES_PASSWORD=$POSTGRES_PASSWORD
ENV POSTGRES_HOST=$POSTGRES_HOST
ENV POSTGRES_PORT=$POSTGRES_PORT
ENV POSTGRES_NAME=$POSTGRES_NAME



CMD ["sh", "-c", "alembic heads && alembic upgrade head"]