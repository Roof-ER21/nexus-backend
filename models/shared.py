"""
Shared Models - Analytics, Logging, Features
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from .database import Base

class AIRequest(Base):
    """Track all AI API requests for cost/performance monitoring"""
    __tablename__ = "ai_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    ai_type = Column(String(20), nullable=False, index=True)  # 'susan' or 'agnes'
    provider = Column(String(50), nullable=False, index=True)  # 'groq', 'together', 'openrouter'
    model = Column(String(100))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    cost_usd = Column(Numeric(10, 6))
    response_time_ms = Column(Integer)
    success = Column(Boolean)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<AIRequest {self.ai_type} via {self.provider}>"

class ActivityLog(Base):
    """User activity logging"""
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(JSONB)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<ActivityLog {self.action}>"

class FeatureUsage(Base):
    """Track feature usage for analytics"""
    __tablename__ = "feature_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    feature_name = Column(String(100), nullable=False, index=True)
    usage_count = Column(Integer, default=1)
    last_used = Column(DateTime(timezone=True), server_default=func.now())
    metadata = Column(JSONB)

    def __repr__(self):
        return f"<FeatureUsage {self.feature_name}>"

class SystemConfig(Base):
    """System-wide configuration"""
    __tablename__ = "system_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(JSONB)
    description = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemConfig {self.key}>"
