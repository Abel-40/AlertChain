from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
engine = create_async_engine(
  settings.DB_URL,
  echo=True,
  pool_size = 10,
  max_overflow = 5
)

AsyncLocalSession = async_sessionmaker(bind=engine,expire_on_commit=False)