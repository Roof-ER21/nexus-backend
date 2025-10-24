"""
Health Check API
System status and monitoring endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Dict

from models.database import get_db
from services.ai_provider import ai_provider_manager
from config import settings

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Comprehensive health check
    Tests: API, Database, AI Providers
    """

    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        status["checks"]["database"] = "healthy"
    except Exception as e:
        status["checks"]["database"] = f"unhealthy: {str(e)}"
        status["status"] = "degraded"

    # Check AI providers
    try:
        ai_stats = ai_provider_manager.get_stats()
        status["checks"]["ai_providers"] = {
            "status": "healthy",
            "total_requests": ai_stats["total_successes"] + ai_stats["total_failures"],
            "success_rate": f"{(ai_stats['total_successes'] / max(ai_stats['total_successes'] + ai_stats['total_failures'], 1)) * 100:.1f}%"
        }
    except Exception as e:
        status["checks"]["ai_providers"] = f"unhealthy: {str(e)}"
        status["status"] = "degraded"

    return status

@router.get("/health/quick")
async def quick_health() -> Dict:
    """Quick health check - no DB/external calls"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/ai")
async def ai_health() -> Dict:
    """AI provider health and statistics"""
    return ai_provider_manager.get_stats()
