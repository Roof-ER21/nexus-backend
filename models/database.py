"""
NEXUS Database Configuration
SQLAlchemy setup with async support and connection pooling
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from config import settings
from loguru import logger

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.ENVIRONMENT == "development",
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # Verify connections before using
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()

async def init_db():
    """Initialize database - create all tables"""
    try:
        async with engine.begin() as conn:
            # Enable extensions
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"pgvector\"")

            # Create all tables
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

async def get_db():
    """Dependency for FastAPI routes - provides database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
