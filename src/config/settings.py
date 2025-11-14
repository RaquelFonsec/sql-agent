from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    openai_api_key: str = Field(..., env='OPENAI_API_KEY')
    database_url: str = Field(..., env='DATABASE_URL')
    postgres_user: str = Field(..., env='POSTGRES_USER')
    postgres_password: str = Field(..., env='POSTGRES_PASSWORD')
    postgres_db: str = Field(..., env='POSTGRES_DB')
    postgres_host: str = Field(default='localhost', env='POSTGRES_HOST')
    postgres_port: int = Field(default=5432, env='POSTGRES_PORT')
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    enable_tracing: bool = Field(default=True, env='ENABLE_TRACING')
    model_name: str = Field(default='gpt-4-turbo-preview')
    temperature: float = Field(default=0.0)
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


settings = Settings()