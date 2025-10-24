"""
NEXUS Backend - Main Application
Dual-AI System for Roofing Training (Susan + Agnes)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from loguru import logger
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO" if os.getenv("ENVIRONMENT") == "production" else "DEBUG"
)
logger.add(
    "logs/nexus_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    level="INFO"
)

# Import configuration
from config import settings

# Import database
from models.database import engine, init_db

# Import routers
from api import auth, susan, agnes, health, analytics

# Sentry integration for production
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
    )
    logger.info("📊 Sentry monitoring initialized")

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    # Startup
    logger.info("🚀 NEXUS Backend Starting...")
    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🤖 AI Providers: Groq, Together, OpenRouter")

    # Initialize database
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    # Initialize AI providers
    try:
        from services.ai_provider import ai_provider_manager
        logger.info(f"✅ AI Providers initialized: {len(ai_provider_manager.providers)} providers")
    except Exception as e:
        logger.error(f"❌ AI Provider initialization failed: {e}")
        raise

    # Load training scenarios
    try:
        from services.agnes_ai import load_training_scenarios
        scenario_count = await load_training_scenarios()
        logger.info(f"✅ Loaded {scenario_count} Agnes training scenarios")
    except Exception as e:
        logger.warning(f"⚠️ Training scenarios not loaded: {e}")

    logger.info("🎉 NEXUS Backend Ready!")

    yield

    # Shutdown
    logger.info("👋 NEXUS Backend Shutting Down...")
    await engine.dispose()
    logger.info("✅ Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="NEXUS API",
    description="Dual-AI System: Susan (Insurance Expert) + Agnes (Training Partner)",
    version="1.0.0",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:3000",  # Next.js dev
    "http://localhost:8000",  # Backend dev
    settings.FRONTEND_URL,
]

if settings.ENVIRONMENT == "production":
    origins.extend([
        "https://sa21-production.up.railway.app",
        "https://*.railway.app",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.ENVIRONMENT != "production" else "An error occurred"
        }
    )

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(susan.router, prefix="/api/susan", tags=["Susan AI"])
app.include_router(agnes.router, prefix="/api/agnes", tags=["Agnes AI"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])

# Root endpoint
@app.get("/")
async def root():
    """API root - system status"""
    return {
        "app": "NEXUS API",
        "version": "1.0.0",
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "ai_systems": {
            "susan": "Insurance Claims Expert",
            "agnes": "Training & Roleplay Partner"
        },
        "docs": "/api/docs" if settings.ENVIRONMENT != "production" else None
    }

# API health check
@app.get("/health")
async def health_check():
    """Quick health check"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }

# Run server
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.ENVIRONMENT == "development",
        log_level="info"
    )
