from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

engine = create_async_engine(
    settings.DB_URL,
    echo=True,
    poolclass=NullPool
)

AsyncLocalSession = async_sessionmaker(
    bind=engine, 
    expire_on_commit=False
)