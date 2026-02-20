"""
Cost tracking service for LLM usage monitoring.

Provides methods to log LLM usage and query cost summaries
by user, operation type, and system-wide.
"""

from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.cost_tracking import LLMUsageLog, OperationType
from app.services.cost_calculator import calculate_cost


class CostTrackingService:
    """Service for tracking and querying LLM usage costs."""

    def __init__(self, db: Session):
        self.db = db

    def log_usage(
        self,
        operation_type: OperationType,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[int] = None,
        product_id: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> LLMUsageLog:
        """
        Log an LLM usage event.

        Args:
            operation_type: The type of operation being performed
            model: The LLM model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user_id: Optional user ID who triggered the call
            product_id: Optional product ID for context
            job_id: Optional job UUID for linking to background jobs

        Returns:
            The created LLMUsageLog record
        """
        estimated_cost = calculate_cost(model, input_tokens, output_tokens)

        log = LLMUsageLog(
            user_id=user_id,
            operation_type=operation_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            product_id=product_id,
            job_id=job_id,
        )

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log

    def get_user_costs(
        self,
        user_id: int,
        days: int = 30
    ) -> dict:
        """
        Get cost summary for a user over the last N days.

        Args:
            user_id: The user ID to query
            days: Number of days to look back (default 30)

        Returns:
            Dict with total cost, request count, and breakdown by operation
        """
        since = datetime.utcnow() - timedelta(days=days)

        logs = self.db.query(LLMUsageLog).filter(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= since
        ).all()

        total_cost = sum(log.estimated_cost_usd for log in logs)
        total_input_tokens = sum(log.input_tokens for log in logs)
        total_output_tokens = sum(log.output_tokens for log in logs)
        by_operation = {}

        for log in logs:
            op = log.operation_type.value
            if op not in by_operation:
                by_operation[op] = {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
            by_operation[op]["count"] += 1
            by_operation[op]["cost"] += log.estimated_cost_usd
            by_operation[op]["input_tokens"] += log.input_tokens
            by_operation[op]["output_tokens"] += log.output_tokens

        # Round costs in by_operation
        for op in by_operation:
            by_operation[op]["cost"] = round(by_operation[op]["cost"], 4)

        return {
            "user_id": user_id,
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "total_requests": len(logs),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "by_operation": by_operation,
        }

    def get_system_costs(
        self,
        days: int = 30
    ) -> dict:
        """
        Get system-wide cost summary.

        Args:
            days: Number of days to look back (default 30)

        Returns:
            Dict with totals, breakdown by operation, and top users
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Total costs
        result = self.db.query(
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("total_cost"),
            func.sum(LLMUsageLog.input_tokens).label("input_tokens"),
            func.sum(LLMUsageLog.output_tokens).label("output_tokens"),
        ).filter(LLMUsageLog.created_at >= since).first()

        # By operation
        by_operation_results = self.db.query(
            LLMUsageLog.operation_type,
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("cost"),
            func.sum(LLMUsageLog.input_tokens).label("input_tokens"),
            func.sum(LLMUsageLog.output_tokens).label("output_tokens"),
        ).filter(
            LLMUsageLog.created_at >= since
        ).group_by(LLMUsageLog.operation_type).all()

        # By user (top 10)
        by_user = self.db.query(
            LLMUsageLog.user_id,
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("cost"),
        ).filter(
            LLMUsageLog.created_at >= since,
            LLMUsageLog.user_id.isnot(None)
        ).group_by(LLMUsageLog.user_id).order_by(
            func.sum(LLMUsageLog.estimated_cost_usd).desc()
        ).limit(10).all()

        # By model
        by_model = self.db.query(
            LLMUsageLog.model,
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.estimated_cost_usd).label("cost"),
        ).filter(
            LLMUsageLog.created_at >= since
        ).group_by(LLMUsageLog.model).all()

        return {
            "period_days": days,
            "total_requests": result.count or 0,
            "total_cost_usd": round(result.total_cost or 0, 4),
            "total_input_tokens": result.input_tokens or 0,
            "total_output_tokens": result.output_tokens or 0,
            "by_operation": {
                op.value: {
                    "count": count,
                    "cost": round(cost, 4),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
                for op, count, cost, input_tokens, output_tokens in by_operation_results
            },
            "by_model": {
                model: {"count": count, "cost": round(cost, 4)}
                for model, count, cost in by_model
            },
            "top_users": [
                {"user_id": uid, "count": count, "cost": round(cost, 4)}
                for uid, count, cost in by_user
            ],
        }

    def get_product_costs(
        self,
        product_id: int,
        days: int = 30
    ) -> dict:
        """
        Get cost summary for a specific product.

        Args:
            product_id: The product ID to query
            days: Number of days to look back (default 30)

        Returns:
            Dict with total cost and breakdown by operation
        """
        since = datetime.utcnow() - timedelta(days=days)

        logs = self.db.query(LLMUsageLog).filter(
            LLMUsageLog.product_id == product_id,
            LLMUsageLog.created_at >= since
        ).all()

        total_cost = sum(log.estimated_cost_usd for log in logs)
        by_operation = {}

        for log in logs:
            op = log.operation_type.value
            if op not in by_operation:
                by_operation[op] = {"count": 0, "cost": 0.0}
            by_operation[op]["count"] += 1
            by_operation[op]["cost"] += log.estimated_cost_usd

        # Round costs
        for op in by_operation:
            by_operation[op]["cost"] = round(by_operation[op]["cost"], 4)

        return {
            "product_id": product_id,
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "total_requests": len(logs),
            "by_operation": by_operation,
        }

    def check_daily_limit(self, limit_usd: float = 50.0) -> bool:
        """
        Check if daily spending exceeds a limit.

        Args:
            limit_usd: The daily spending limit in USD (default $50)

        Returns:
            True if daily spending exceeds the limit
        """
        today = datetime.utcnow().date()

        total = self.db.query(
            func.sum(LLMUsageLog.estimated_cost_usd)
        ).filter(
            func.date(LLMUsageLog.created_at) == today
        ).scalar() or 0

        return total > limit_usd

    def get_daily_cost(self) -> float:
        """
        Get today's total cost.

        Returns:
            Today's total estimated cost in USD
        """
        today = datetime.utcnow().date()

        total = self.db.query(
            func.sum(LLMUsageLog.estimated_cost_usd)
        ).filter(
            func.date(LLMUsageLog.created_at) == today
        ).scalar() or 0

        return round(total, 4)
