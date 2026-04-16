"""
DEPRECATED: Legacy workflow orchestration module.

This module contained the WorkflowService class for the old session-based
competitive analysis pipeline (product analysis -> competitor discovery ->
feature extraction).

The V2 competitive intelligence workflow uses:
- functional_audit_task: Runs functional analysis for competitors
- unified_synthesis_task: Synthesizes opportunities across all sources

Use the V2 workflow via the competitive_agents.py API endpoints:
- POST /{product_id}/run-competitive-analysis-v2
- POST /unified-synthesis/{product_id}/run
"""

# This file is kept for documentation purposes.
# All workflow functionality has been moved to:
# - backend/app/queue/tasks.py (functional_audit_task, unified_synthesis_task)
# - backend/app/api/competitive_agents.py + backend/app/api/unified_synthesis.py
