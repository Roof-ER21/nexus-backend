"""
Analytics API
Usage tracking, cost monitoring, feature analytics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date
from uuid import UUID

from models import (
    User, UserRole, AIRequest, ActivityLog, FeatureUsage,
    SusanConversation, TrainingSession, ScenarioResult
)
from models.database import get_db
from api.auth import get_current_user
from loguru import logger

router = APIRouter()

# Pydantic models
class UsageStats(BaseModel):
    total_ai_requests: int
    total_cost: float
    susan_requests: int
    susan_cost: float
    agnes_requests: int
    agnes_cost: float
    average_response_time_ms: float
    success_rate: float

class CostBreakdown(BaseModel):
    date: str
    total_cost: float
    susan_cost: float
    agnes_cost: float
    requests: int

class ProviderStats(BaseModel):
    provider: str
    requests: int
    cost: float
    average_response_time_ms: float
    success_rate: float

class FeatureStats(BaseModel):
    feature: str
    usage_count: int
    unique_users: int
    last_used: datetime

class UserActivity(BaseModel):
    date: str
    active_users: int
    new_users: int
    conversations_started: int
    scenarios_completed: int

class SystemHealth(BaseModel):
    status: str
    total_users: int
    active_today: int
    ai_success_rate: float
    average_response_time_ms: float
    total_cost_today: float
    alerts: List[str]

# Helper function for admin check
async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Routes
@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall usage statistics
    Admin only
    """

    since_date = datetime.utcnow() - timedelta(days=days)

    # Total AI requests
    total_result = await db.execute(
        select(func.count(AIRequest.id)).where(
            AIRequest.created_at >= since_date
        )
    )
    total_requests = total_result.scalar() or 0

    # Total cost
    cost_result = await db.execute(
        select(func.sum(AIRequest.cost)).where(
            AIRequest.created_at >= since_date
        )
    )
    total_cost = float(cost_result.scalar() or 0)

    # Susan stats
    susan_result = await db.execute(
        select(
            func.count(AIRequest.id).label('count'),
            func.sum(AIRequest.cost).label('cost')
        ).where(
            and_(
                AIRequest.ai_type == "susan",
                AIRequest.created_at >= since_date
            )
        )
    )
    susan_data = susan_result.first()
    susan_requests = susan_data.count or 0
    susan_cost = float(susan_data.cost or 0)

    # Agnes stats
    agnes_result = await db.execute(
        select(
            func.count(AIRequest.id).label('count'),
            func.sum(AIRequest.cost).label('cost')
        ).where(
            and_(
                AIRequest.ai_type == "agnes",
                AIRequest.created_at >= since_date
            )
        )
    )
    agnes_data = agnes_result.first()
    agnes_requests = agnes_data.count or 0
    agnes_cost = float(agnes_data.cost or 0)

    # Average response time
    response_time_result = await db.execute(
        select(func.avg(AIRequest.response_time_ms)).where(
            and_(
                AIRequest.created_at >= since_date,
                AIRequest.success == True
            )
        )
    )
    avg_response_time = float(response_time_result.scalar() or 0)

    # Success rate
    success_result = await db.execute(
        select(func.count(AIRequest.id)).where(
            and_(
                AIRequest.created_at >= since_date,
                AIRequest.success == True
            )
        )
    )
    success_count = success_result.scalar() or 0
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0

    return UsageStats(
        total_ai_requests=total_requests,
        total_cost=total_cost,
        susan_requests=susan_requests,
        susan_cost=susan_cost,
        agnes_requests=agnes_requests,
        agnes_cost=agnes_cost,
        average_response_time_ms=avg_response_time,
        success_rate=success_rate
    )

@router.get("/cost-breakdown", response_model=List[CostBreakdown])
async def get_cost_breakdown(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily cost breakdown
    Admin only
    """

    since_date = datetime.utcnow() - timedelta(days=days)

    # Query daily costs
    result = await db.execute(
        select(
            func.date(AIRequest.created_at).label('date'),
            func.sum(AIRequest.cost).label('total_cost'),
            func.sum(
                func.case((AIRequest.ai_type == 'susan', AIRequest.cost), else_=0)
            ).label('susan_cost'),
            func.sum(
                func.case((AIRequest.ai_type == 'agnes', AIRequest.cost), else_=0)
            ).label('agnes_cost'),
            func.count(AIRequest.id).label('requests')
        )
        .where(AIRequest.created_at >= since_date)
        .group_by(func.date(AIRequest.created_at))
        .order_by(func.date(AIRequest.created_at))
    )

    breakdown = [
        CostBreakdown(
            date=row.date.isoformat(),
            total_cost=float(row.total_cost or 0),
            susan_cost=float(row.susan_cost or 0),
            agnes_cost=float(row.agnes_cost or 0),
            requests=row.requests
        )
        for row in result.all()
    ]

    return breakdown

@router.get("/providers", response_model=List[ProviderStats])
async def get_provider_stats(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics by AI provider
    Admin only
    """

    since_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            AIRequest.provider,
            func.count(AIRequest.id).label('requests'),
            func.sum(AIRequest.cost).label('cost'),
            func.avg(AIRequest.response_time_ms).label('avg_response_time'),
            func.sum(func.case((AIRequest.success == True, 1), else_=0)).label('successes')
        )
        .where(AIRequest.created_at >= since_date)
        .group_by(AIRequest.provider)
    )

    stats = []
    for row in result.all():
        success_rate = (row.successes / row.requests * 100) if row.requests > 0 else 0
        stats.append(ProviderStats(
            provider=row.provider,
            requests=row.requests,
            cost=float(row.cost or 0),
            average_response_time_ms=float(row.avg_response_time or 0),
            success_rate=success_rate
        ))

    return stats

@router.get("/features", response_model=List[FeatureStats])
async def get_feature_stats(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get feature usage statistics
    Admin only
    """

    since_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            FeatureUsage.feature_name,
            func.count(FeatureUsage.id).label('usage_count'),
            func.count(func.distinct(FeatureUsage.user_id)).label('unique_users'),
            func.max(FeatureUsage.used_at).label('last_used')
        )
        .where(FeatureUsage.used_at >= since_date)
        .group_by(FeatureUsage.feature_name)
        .order_by(desc('usage_count'))
    )

    stats = [
        FeatureStats(
            feature=row.feature_name,
            usage_count=row.usage_count,
            unique_users=row.unique_users,
            last_used=row.last_used
        )
        for row in result.all()
    ]

    return stats

@router.get("/activity", response_model=List[UserActivity])
async def get_user_activity(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily user activity metrics
    Admin only
    """

    since_date = datetime.utcnow() - timedelta(days=days)

    # Daily active users
    active_users_result = await db.execute(
        select(
            func.date(ActivityLog.created_at).label('date'),
            func.count(func.distinct(ActivityLog.user_id)).label('active_users')
        )
        .where(ActivityLog.created_at >= since_date)
        .group_by(func.date(ActivityLog.created_at))
    )
    active_users_by_date = {row.date: row.active_users for row in active_users_result.all()}

    # New users
    new_users_result = await db.execute(
        select(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('new_users')
        )
        .where(User.created_at >= since_date)
        .group_by(func.date(User.created_at))
    )
    new_users_by_date = {row.date: row.new_users for row in new_users_result.all()}

    # Conversations started
    conversations_result = await db.execute(
        select(
            func.date(SusanConversation.created_at).label('date'),
            func.count(SusanConversation.id).label('conversations')
        )
        .where(SusanConversation.created_at >= since_date)
        .group_by(func.date(SusanConversation.created_at))
    )
    conversations_by_date = {row.date: row.conversations for row in conversations_result.all()}

    # Scenarios completed
    scenarios_result = await db.execute(
        select(
            func.date(ScenarioResult.completed_at).label('date'),
            func.count(ScenarioResult.id).label('scenarios')
        )
        .where(ScenarioResult.completed_at >= since_date)
        .group_by(func.date(ScenarioResult.completed_at))
    )
    scenarios_by_date = {row.date: row.scenarios for row in scenarios_result.all()}

    # Combine all metrics
    all_dates = set(active_users_by_date.keys()) | set(new_users_by_date.keys()) | \
                 set(conversations_by_date.keys()) | set(scenarios_by_date.keys())

    activity = []
    for date_obj in sorted(all_dates):
        activity.append(UserActivity(
            date=date_obj.isoformat(),
            active_users=active_users_by_date.get(date_obj, 0),
            new_users=new_users_by_date.get(date_obj, 0),
            conversations_started=conversations_by_date.get(date_obj, 0),
            scenarios_completed=scenarios_by_date.get(date_obj, 0)
        ))

    return activity

@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current system health status
    Admin only
    """

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    # Total users
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.active == True)
    )
    total_users = total_users_result.scalar() or 0

    # Active today
    active_today_result = await db.execute(
        select(func.count(func.distinct(ActivityLog.user_id))).where(
            ActivityLog.created_at >= today_start
        )
    )
    active_today = active_today_result.scalar() or 0

    # AI success rate (last 24 hours)
    ai_stats_result = await db.execute(
        select(
            func.count(AIRequest.id).label('total'),
            func.sum(func.case((AIRequest.success == True, 1), else_=0)).label('successes'),
            func.avg(AIRequest.response_time_ms).label('avg_response_time')
        ).where(AIRequest.created_at >= today_start)
    )
    ai_stats = ai_stats_result.first()
    ai_success_rate = (ai_stats.successes / ai_stats.total * 100) if ai_stats.total > 0 else 100
    avg_response_time = float(ai_stats.avg_response_time or 0)

    # Cost today
    cost_today_result = await db.execute(
        select(func.sum(AIRequest.cost)).where(
            AIRequest.created_at >= today_start
        )
    )
    cost_today = float(cost_today_result.scalar() or 0)

    # Generate alerts
    alerts = []

    if ai_success_rate < 95:
        alerts.append(f"AI success rate below 95%: {ai_success_rate:.1f}%")

    if avg_response_time > 5000:
        alerts.append(f"High average response time: {avg_response_time:.0f}ms")

    if cost_today > 10:  # Alert if daily cost exceeds $10
        alerts.append(f"Daily cost high: ${cost_today:.2f}")

    if active_today < total_users * 0.1:  # Less than 10% active
        alerts.append(f"Low user activity: {active_today}/{total_users} active")

    # Determine overall status
    if len(alerts) == 0:
        status = "healthy"
    elif len(alerts) <= 2:
        status = "warning"
    else:
        status = "critical"

    return SystemHealth(
        status=status,
        total_users=total_users,
        active_today=active_today,
        ai_success_rate=ai_success_rate,
        average_response_time_ms=avg_response_time,
        total_cost_today=cost_today,
        alerts=alerts
    )

@router.get("/user/{user_id}/stats")
async def get_user_stats(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics for specific user
    Admin can view any user, users can view themselves
    """

    # Permission check
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        if str(current_user.id) != str(user_id):
            raise HTTPException(status_code=403, detail="Cannot view other user stats")

    # User info
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Susan usage
    susan_result = await db.execute(
        select(
            func.count(SusanConversation.id).label('conversations'),
            func.sum(SusanConversation.message_count).label('messages')
        ).where(SusanConversation.user_id == user_id)
    )
    susan_data = susan_result.first()

    # Agnes usage
    agnes_result = await db.execute(
        select(
            func.count(TrainingSession.id).label('sessions'),
            func.count(
                func.case((TrainingSession.completed == True, 1))
            ).label('completed'),
            func.avg(TrainingSession.final_score).label('avg_score')
        ).where(TrainingSession.user_id == user_id)
    )
    agnes_data = agnes_result.first()

    # Recent activity
    activity_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == user_id)
        .order_by(desc(ActivityLog.created_at))
        .limit(20)
    )
    recent_activity = [
        {
            "activity_type": log.activity_type,
            "details": log.details,
            "created_at": log.created_at.isoformat()
        }
        for log in activity_result.scalars().all()
    ]

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None
        },
        "susan_usage": {
            "conversations": susan_data.conversations or 0,
            "messages": susan_data.messages or 0
        },
        "agnes_usage": {
            "training_sessions": agnes_data.sessions or 0,
            "completed_scenarios": agnes_data.completed or 0,
            "average_score": float(agnes_data.avg_score or 0)
        },
        "recent_activity": recent_activity
    }

@router.post("/activity")
async def log_activity(
    activity_type: str,
    details: Optional[Dict] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Log user activity
    Used by frontend to track feature usage
    """

    activity = ActivityLog(
        user_id=current_user.id,
        activity_type=activity_type,
        details=details or {}
    )
    db.add(activity)
    await db.commit()

    return {"message": "Activity logged"}

@router.post("/feature-usage")
async def log_feature_usage(
    feature_name: str,
    metadata: Optional[Dict] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Log feature usage
    Used for analytics and feature adoption tracking
    """

    usage = FeatureUsage(
        user_id=current_user.id,
        feature_name=feature_name,
        metadata=metadata or {}
    )
    db.add(usage)
    await db.commit()

    return {"message": "Feature usage logged"}

@router.get("/export/ai-costs")
async def export_ai_costs(
    start_date: date,
    end_date: date,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Export detailed AI cost data for analysis
    Admin only
    Returns CSV-ready data
    """

    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    result = await db.execute(
        select(AIRequest)
        .where(
            and_(
                AIRequest.created_at >= start_datetime,
                AIRequest.created_at <= end_datetime
            )
        )
        .order_by(AIRequest.created_at)
    )
    requests = result.scalars().all()

    # Format as CSV data
    csv_data = [
        {
            "timestamp": req.created_at.isoformat(),
            "user_id": str(req.user_id),
            "ai_type": req.ai_type,
            "provider": req.provider,
            "model": req.model,
            "prompt_tokens": req.prompt_tokens,
            "completion_tokens": req.completion_tokens,
            "total_tokens": req.total_tokens,
            "cost": float(req.cost),
            "response_time_ms": req.response_time_ms,
            "success": req.success
        }
        for req in requests
    ]

    logger.info(f"Admin {current_user.email} exported {len(csv_data)} AI cost records")

    return {"data": csv_data, "total_records": len(csv_data)}
