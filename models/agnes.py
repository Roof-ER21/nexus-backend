"""
Agnes AI Models - Training & Roleplay System
115 Roof-ER insurance claims scenarios
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from .database import Base

class ScenarioDifficulty(str, enum.Enum):
    """Scenario difficulty levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"
    CHALLENGE = "challenge"

class ScenarioCategory(str, enum.Enum):
    """Scenario categories matching Roof-ER workflow"""
    INITIAL_CONTACT = "initial_contact"
    INSPECTION_DOCUMENTATION = "inspection_documentation"
    ADJUSTER_RELATIONS = "adjuster_relations"
    TEMPLATE_MASTERY = "template_mastery"
    ESCALATION_PROCESS = "escalation_process"
    COMPLEX_SCENARIOS = "complex_scenarios"

class PerformanceTier(str, enum.Enum):
    """Performance tier based on score"""
    BRONZE = "bronze"      # 0-69
    SILVER = "silver"      # 70-84
    GOLD = "gold"          # 85-94
    PLATINUM = "platinum"  # 95-100+

class TrainingScenario(Base):
    """Individual training scenarios (115 total)"""
    __tablename__ = "training_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "scenario_1_1"
    category = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    difficulty = Column(String(20), nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    description = Column(Text)

    # Character profiles
    homeowner_profile = Column(JSONB)  # Name, age, personality, concerns
    adjuster_profile = Column(JSONB)   # For adjuster scenarios
    team_leader_profile = Column(JSONB)  # For escalation scenarios

    # Scenario content
    initial_message = Column(Text)  # Agnes's first message
    scenario_script = Column(JSONB)  # Branching dialogue tree
    grading_criteria = Column(JSONB)  # Points breakdown
    learning_objectives = Column(JSONB)

    # Roof-ER specific
    templates_referenced = Column(JSONB)  # Photo Report, iTel, etc.
    codes_referenced = Column(JSONB)  # IBC, IRC, GAF guidelines
    manufacturer_refs = Column(JSONB)  # GAF, Owens Corning docs

    # Metadata
    max_score = Column(Integer, default=100)
    bonus_available = Column(Integer, default=0)
    tags = Column(JSONB)  # Search tags
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    active = Column(Boolean, default=True)

    # Relationships
    sessions = relationship("TrainingSession", back_populates="scenario")

    def __repr__(self):
        return f"<TrainingScenario {self.scenario_id}: {self.title}>"

class TrainingSession(Base):
    """Individual training session instance"""
    __tablename__ = "training_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("training_scenarios.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    final_score = Column(Integer)
    tier = Column(String(20))  # bronze, silver, gold, platinum
    archived = Column(Boolean, default=False)

    # Session metadata
    context = Column(JSONB)  # Any additional context
    user_notes = Column(Text)

    # Relationships
    user = relationship("User", back_populates="training_sessions")
    scenario = relationship("TrainingScenario", back_populates="sessions")
    messages = relationship("TrainingMessage", back_populates="session", cascade="all, delete-orphan")
    result = relationship("ScenarioResult", back_populates="session", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TrainingSession {self.id} - Score: {self.final_score}>"

class TrainingMessage(Base):
    """Messages within a training session"""
    __tablename__ = "training_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'homeowner', 'adjuster', 'system'
    content = Column(Text, nullable=False)
    score_change = Column(Integer, default=0)
    feedback = Column(Text)  # Real-time feedback from Agnes
    metadata = Column(JSONB)  # Additional context
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("TrainingSession", back_populates="messages")

    def __repr__(self):
        return f"<TrainingMessage {self.role}: {self.content[:50]}...>"

class ScenarioResult(Base):
    """Detailed results and feedback for completed scenario"""
    __tablename__ = "scenario_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=False, unique=True)
    category_scores = Column(JSONB)  # Breakdown by grading category
    feedback = Column(JSONB)  # What went well, areas to improve
    badges_earned = Column(JSONB)  # New badges from this session
    improvement_areas = Column(JSONB)  # Specific recommendations
    recommended_next = Column(JSONB)  # Next scenarios to try
    top_moment = Column(Text)  # Best response in scenario
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("TrainingSession", back_populates="result")

    def __repr__(self):
        return f"<ScenarioResult for session {self.session_id}>"

class UserTrainingProgress(Base):
    """Aggregate training progress for each user"""
    __tablename__ = "user_training_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    total_scenarios_completed = Column(Integer, default=0)
    average_score = Column(Numeric(5, 2))
    current_tier = Column(String(20))  # Overall tier
    total_training_hours = Column(Numeric(6, 2), default=0)
    badges_earned = Column(JSONB, default=list)  # List of badge IDs
    skill_scores = Column(JSONB, default=dict)  # Breakdown by skill area

    # Category completion tracking
    initial_contact_completed = Column(Integer, default=0)
    inspection_completed = Column(Integer, default=0)
    adjuster_completed = Column(Integer, default=0)
    template_completed = Column(Integer, default=0)
    escalation_completed = Column(Integer, default=0)
    complex_completed = Column(Integer, default=0)

    # Streaks and challenges
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_activity = Column(DateTime(timezone=True))
    challenges_completed = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="training_progress")

    def __repr__(self):
        return f"<UserTrainingProgress {self.user_id} - {self.total_scenarios_completed} scenarios>"

class TrainingBadge(Base):
    """Achievement badges (50 total)"""
    __tablename__ = "training_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    badge_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50))  # documentation, adjuster, knowledge, communication, escalation
    description = Column(Text)
    criteria = Column(JSONB)  # How to earn it
    icon_url = Column(String(500))
    icon_emoji = Column(String(10))  # Fallback emoji
    rarity = Column(String(20), default="common")  # common, rare, epic, legendary
    points_value = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user_badges = relationship("UserBadge", back_populates="badge")

    def __repr__(self):
        return f"<TrainingBadge {self.name} ({self.rarity})>"

class UserBadge(Base):
    """User's earned badges"""
    __tablename__ = "user_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    badge_id = Column(UUID(as_uuid=True), ForeignKey("training_badges.id"), nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("training_scenarios.id"))  # Which scenario earned it

    # Unique constraint: user can only earn each badge once
    __table_args__ = (
        {'extend_existing': True},
    )

    # Relationships
    user = relationship("User", back_populates="earned_badges")
    badge = relationship("TrainingBadge", back_populates="user_badges")

    def __repr__(self):
        return f"<UserBadge {self.user_id} earned {self.badge_id}>"

class DailyChallenge(Base):
    """Daily training challenges"""
    __tablename__ = "daily_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("training_scenarios.id"))
    description = Column(Text)
    bonus_points = Column(Integer, default=50)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    completions = relationship("ChallengeCompletion", back_populates="challenge")

    def __repr__(self):
        return f"<DailyChallenge {self.challenge_date}>"

class ChallengeCompletion(Base):
    """Track daily challenge completions"""
    __tablename__ = "challenge_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("daily_challenges.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    score = Column(Integer)
    bonus_earned = Column(Integer)

    # Unique constraint: user can only complete each challenge once
    __table_args__ = (
        {'extend_existing': True},
    )

    # Relationships
    challenge = relationship("DailyChallenge", back_populates="completions")

    def __repr__(self):
        return f"<ChallengeCompletion {self.user_id} - Challenge {self.challenge_id}>"

class Leaderboard(Base):
    """Leaderboard snapshots"""
    __tablename__ = "leaderboards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period = Column(String(20), nullable=False, index=True)  # daily, weekly, monthly, all_time
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True))
    rankings = Column(JSONB)  # Top performers with scores
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Leaderboard {self.period} - {self.period_start}>"
