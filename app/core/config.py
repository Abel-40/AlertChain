from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
class Settings(BaseSettings):
  DB_HOST:str
  DB_USERNAME:str
  DB_PORT:str
  DB_PASSWORD:str
  DB_NAME:str
  REDIS_FOR_CACHE:str
  REDIS_FOR_BROKER:str
  REDIS_FOR_BACKEND:str
  ACCESS_TOKEN_KEY:str
  REFRESH_TOKEN_KEY:str
  ALGO:str
  @property
  def DB_URL(self):
    url = f"postgresql+asyncpg://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    return url
  
  class Config:
    env_file = BASE_DIR / ".env"
    extra = "ignore"
  
settings = Settings()