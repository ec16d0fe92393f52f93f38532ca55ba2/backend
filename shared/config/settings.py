import os
from typing import List

# from anyio.functools import lru_cache
from pydantic import AnyHttpUrl, BaseModel, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import URL


class PostgresPool(BaseModel):
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_echo: bool = True

class RedisSettings(BaseModel):
    redis_password: str = "password"
    redis_user: str = "username"
    redis_user_password: str = "password"
    redis_host: str = "localhost"
    redis_port: int = 6379


class PostgresSettings(BaseModel):
    postgres_host: str
    postgres_port: int
    postgres_username: str
    postgres_password: str
    postgres_database: str
    pool: PostgresPool = PostgresPool()






class MongoSettings(BaseSettings):
    mongo_host: str = 'localhost'
    mongo_port: int = 27017





class SharedSettings(BaseModel):
    cors_origin: List[AnyHttpUrl] = ["http://localhost:5173", "http://localhost:8080"]
    allowed_hosts: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]


class Settings(BaseSettings):
    shared_settings: SharedSettings = SharedSettings()
    postgres_settings: PostgresSettings
    mongo_settings: MongoSettings = MongoSettings()
    redis_settings: RedisSettings = RedisSettings()

    @computed_field
    @property
    def sqlalchemy_database_setting(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_settings.postgres_username,
            password=self.postgres_settings.postgres_password,
            host=self.postgres_settings.postgres_host,
            port=self.postgres_settings.postgres_port,
            database=self.postgres_settings.postgres_database,
        )

    model_config = SettingsConfigDict(
        env_file=(".env",),
        case_sensitive=False,
        env_nested_delimiter="__"
    )


# @lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings() #type: ignore


