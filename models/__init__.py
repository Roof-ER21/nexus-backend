"""
NEXUS Models Package
Import all models for easy access
"""

from .database import Base, engine, AsyncSessionLocal, init_db, get_db
from .user import User, Company, UserRole
from .susan import (
    SusanConversation,
    SusanMessage,
    KnowledgeBase,
    BuildingCode,
    Manufacturer,
    InsuranceCarrier,
    ProcessedDocument,
    EmailTemplate,
    GeneratedEmail,
    WeatherEvent,
)
from .agnes import (
    TrainingScenario,
    TrainingSession,
    TrainingMessage,
    ScenarioResult,
    UserTrainingProgress,
    TrainingBadge,
    UserBadge,
    DailyChallenge,
    ChallengeCompletion,
    Leaderboard,
    ScenarioDifficulty,
    ScenarioCategory,
    PerformanceTier,
)
from .shared import (
    AIRequest,
    ActivityLog,
    FeatureUsage,
    SystemConfig,
)

__all__ = [
    # Database
    "Base",
    "engine",
    "AsyncSessionLocal",
    "init_db",
    "get_db",
    # User models
    "User",
    "Company",
    "UserRole",
    # Susan AI models
    "SusanConversation",
    "SusanMessage",
    "KnowledgeBase",
    "BuildingCode",
    "Manufacturer",
    "InsuranceCarrier",
    "ProcessedDocument",
    "EmailTemplate",
    "GeneratedEmail",
    "WeatherEvent",
    # Agnes AI models
    "TrainingScenario",
    "TrainingSession",
    "TrainingMessage",
    "ScenarioResult",
    "UserTrainingProgress",
    "TrainingBadge",
    "UserBadge",
    "DailyChallenge",
    "ChallengeCompletion",
    "Leaderboard",
    "ScenarioDifficulty",
    "ScenarioCategory",
    "PerformanceTier",
    # Shared models
    "AIRequest",
    "ActivityLog",
    "FeatureUsage",
    "SystemConfig",
]
