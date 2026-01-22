"""
DEPRECATED: Legacy workflow orchestration module.

This module contained the WorkflowService class for the old session-based
competitive analysis pipeline (product analysis → competitor discovery →
feature extraction).

This has been replaced by the V2 Competitive Intelligence Agent workflow:
- functional_audit_task: Runs functional analysis for competitors
- landscape_synthesis_task: Synthesizes opportunities across competitors

Use the V2 workflow via the competitive_agents.py API endpoints:
- POST /{product_id}/run-competitive-analysis-v2
- POST /{product_id}/run-landscape-synthesis
"""

# This file is kept for documentation purposes.
# All workflow functionality has been moved to:
# - backend/app/queue/tasks.py (functional_audit_task, landscape_synthesis_task)
# - backend/app/api/competitive_agents.py (API endpoints)
