"""
Database models package.

Import all models here to make them available throughout the app.
"""

from app.models.user import User, UserRole, ProductAccessMode
from app.models.idea import Idea, SourceType, IdeaStatus
from app.models.idea_comment import IdeaComment
from app.models.idea_status_history import IdeaStatusHistory
from app.models.vote import Vote
from app.models.submission import Submission
from app.models.password_reset import PasswordResetToken
from app.models.competitor_intelligence import (
    CIProduct,
    CompetitorAnalysisSession,
    ProductCompetitor,
    SessionCompetitor,
    ProductCompetitorFeature,
    CompetitorFeature,
    CompetitorGeneratedIdea,
    AgentExecutionLog,
    ProductPermission,
    ProductPermissionLevel,
    ProductAnalysisHistory
)
from app.models.queue import QueueJob, JobType, JobStatus, JobPriority
from app.models.pm_review import (
    PMReviewQueue,
    CompetitorSnapshot,
    MonitoringConfig,
    ReviewQueueType,
    ReviewQueueStatus,
    ReviewQueuePriority,
    AlertType
)
from app.models.competitive_agent import (
    AgentMode,
    CompetitiveAgentConfig,
    FeatureCluster,
    FeatureClusterMember,
)
from app.models.competitive_reports import (
    CompetitorFunctionalReport,
    LandscapeOpportunityReport,
)
from app.models.internal_feedback import (
    InternalFeedbackImport,
    WinLossTheme,
    SupportTheme,
    ImportStatus,
)
from app.models.synthesis import (
    SynthesisRun,
    SynthesizedOpportunity,
    SynthesisStatus,
    SourceType as SynthesisSourceType,
)

__all__ = [
    "User", "UserRole", "ProductAccessMode",
    "Idea", "SourceType", "IdeaStatus", "IdeaComment", "IdeaStatusHistory",
    "Vote", "Submission", "PasswordResetToken",
    "CIProduct", "CompetitorAnalysisSession", "ProductCompetitor", "SessionCompetitor",
    "ProductCompetitorFeature", "CompetitorFeature", "CompetitorGeneratedIdea", "AgentExecutionLog",
    "ProductPermission", "ProductPermissionLevel", "ProductAnalysisHistory",
    "QueueJob", "JobType", "JobStatus", "JobPriority",
    "PMReviewQueue", "CompetitorSnapshot", "MonitoringConfig",
    "ReviewQueueType", "ReviewQueueStatus", "ReviewQueuePriority", "AlertType",
    "AgentMode", "CompetitiveAgentConfig", "FeatureCluster", "FeatureClusterMember",
    "CompetitorFunctionalReport", "LandscapeOpportunityReport",
    "InternalFeedbackImport", "WinLossTheme", "SupportTheme", "ImportStatus",
    "SynthesisRun", "SynthesizedOpportunity", "SynthesisStatus", "SynthesisSourceType",
]
