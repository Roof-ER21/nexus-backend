"""
User and Company Models
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from .database import Base

class UserRole(str, enum.Enum):
    """User role enumeration"""
    REP = "rep"
    TEAM_LEADER = "team_leader"
    SALES_MANAGER = "sales_manager"
    MANAGER = "manager"
    ADMIN = "admin"

class Company(Base):
    """Company model"""
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    phone = Column(String(50))
    email = Column(String(255))
    subscription_tier = Column(String(50), default="pro")  # free, pro, enterprise
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    active = Column(Boolean, default=True)

    # Relationships
    users = relationship("User", back_populates="company")

class User(Base):
    """User model with authentication"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.REP)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)

    # Profile fields
    phone = Column(String(50))
    avatar_url = Column(String(500))
    timezone = Column(String(50), default="America/New_York")

    # Relationships
    company = relationship("Company", back_populates="users")
    susan_conversations = relationship("SusanConversation", back_populates="user")
    training_sessions = relationship("TrainingSession", back_populates="user")
    training_progress = relationship("UserTrainingProgress", back_populates="user", uselist=False)
    earned_badges = relationship("UserBadge", back_populates="user")

    def __repr__(self):
        return f"<User {self.email}>"
