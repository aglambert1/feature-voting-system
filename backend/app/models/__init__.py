"""
Database models package.

Import all models here to make them available throughout the app.
"""

from app.models.user import User, UserRole, ProductAccessMode
from app.models.idea import Idea, SourceType, IdeaStatus
from app.models.idea_lifecycle_status import IdeaLifecycleStatus
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
from app.models.activity_insights import (
    ActivityImport,
    DealActivityInsight,
    SupportActivityInsight,
)
from app.models.synthesis import (
    SynthesisRun,
    SynthesizedOpportunity,
    SynthesisStatus,
    SourceType as SynthesisSourceType,
)
from app.models.cost_tracking import (
    LLMUsageLog,
    OperationType,
)
from app.models.product_invite import ProductInviteCode
from app.models.evidence import Evidence, EvidenceType
from app.models.api_key import UserAPIKey
from mcp_server.oauth_models import OAuthClient, OAuthAuthorizationCode, OAuthRefreshToken

__all__ = [
    "User", "UserRole", "ProductAccessMode",
    "Idea", "SourceType", "IdeaStatus", "IdeaLifecycleStatus", "IdeaComment", "IdeaStatusHistory",
    "Vote", "Submission", "PasswordResetToken",
    "CIProduct", "CompetitorAnalysisSession", "ProductCompetitor", "SessionCompetitor",
    "ProductCompetitorFeature", "CompetitorFeature", "CompetitorGeneratedIdea", "AgentExecutionLog",
    "ProductPermission", "ProductPermissionLevel", "ProductAnalysisHistory",
    "QueueJob", "JobType", "JobStatus", "JobPriority",
    "PMReviewQueue", "CompetitorSnapshot", "MonitoringConfig",
    "ReviewQueueType", "ReviewQueueStatus", "ReviewQueuePriority", "AlertType",
    "AgentMode", "CompetitiveAgentConfig",
    "CompetitorFunctionalReport", "LandscapeOpportunityReport",
    "InternalFeedbackImport", "WinLossTheme", "SupportTheme", "ImportStatus",
    "ActivityImport", "DealActivityInsight", "SupportActivityInsight",
    "SynthesisRun", "SynthesizedOpportunity", "SynthesisStatus", "SynthesisSourceType",
    "LLMUsageLog", "OperationType",
    "ProductInviteCode",
    "Evidence", "EvidenceType",
    "UserAPIKey",
    "OAuthClient", "OAuthAuthorizationCode", "OAuthRefreshToken",
]
