"""Competitive monitoring tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access

from app.models.competitor_intelligence import ProductPermissionLevel


@mcp.tool()
def monitoring_get_config(product_id: int) -> dict:
    """Get the competitive monitoring configuration for a product — frequency, alert settings, auto-idea generation.

    Args:
        product_id: The product to get monitoring config for.
    """
    from app.services.pm_review_service import PMReviewService

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        service = PMReviewService(db)
        config = service.get_monitoring_config(product_id)

        if not config:
            return {
                "product_id": product_id,
                "configured": False,
                "monitoring_enabled": False,
                "message": "No monitoring config exists. Use monitoring_update_config to set one up.",
            }

        return {
            "product_id": product_id,
            "configured": True,
            "monitoring_enabled": config.monitoring_enabled,
            "monitoring_frequency": config.monitoring_frequency,
            "last_monitored_at": config.last_monitored_at.isoformat() if config.last_monitored_at else None,
            "next_scheduled_at": config.next_scheduled_at.isoformat() if config.next_scheduled_at else None,
            "alert_on_new_features": config.alert_on_new_features,
            "alert_on_removed_features": config.alert_on_removed_features,
            "alert_on_new_competitors": config.alert_on_new_competitors,
            "min_feature_change_threshold": config.min_feature_change_threshold,
            "auto_generate_ideas": config.auto_generate_ideas,
            "auto_idea_confidence_threshold": config.auto_idea_confidence_threshold,
            "notify_product_owners": config.notify_product_owners,
        }


@mcp.tool()
def monitoring_update_config(
    product_id: int,
    monitoring_enabled: bool = None,
    monitoring_frequency: str = None,
    alert_on_new_features: bool = None,
    alert_on_removed_features: bool = None,
    alert_on_new_competitors: bool = None,
    min_feature_change_threshold: int = None,
    auto_generate_ideas: bool = None,
    auto_idea_confidence_threshold: float = None,
    notify_product_owners: bool = None,
) -> dict:
    """Update competitive monitoring configuration. Only provided fields are changed.

    Args:
        product_id: The product to configure monitoring for.
        monitoring_enabled: Enable or disable monitoring.
        monitoring_frequency: How often to monitor: "daily", "weekly", "biweekly", "monthly".
        alert_on_new_features: Alert when competitors add features.
        alert_on_removed_features: Alert when competitors remove features.
        alert_on_new_competitors: Alert on new competitors discovered.
        min_feature_change_threshold: Minimum features changed to trigger an alert (1+).
        auto_generate_ideas: Automatically create ideas from detected competitor features.
        auto_idea_confidence_threshold: Confidence threshold for auto-generated ideas (0.0-1.0).
        notify_product_owners: Send notifications to product owners on changes.
    """
    from app.services.pm_review_service import PMReviewService

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Validate frequency
        if monitoring_frequency:
            valid_frequencies = {"daily", "weekly", "biweekly", "monthly"}
            if monitoring_frequency not in valid_frequencies:
                return {"error": f"Invalid frequency '{monitoring_frequency}'. Must be one of: {sorted(valid_frequencies)}"}

        # Validate threshold
        if auto_idea_confidence_threshold is not None:
            if not 0.0 <= auto_idea_confidence_threshold <= 1.0:
                return {"error": "auto_idea_confidence_threshold must be between 0.0 and 1.0"}

        if min_feature_change_threshold is not None:
            if min_feature_change_threshold < 1:
                return {"error": "min_feature_change_threshold must be at least 1"}

        service = PMReviewService(db)

        # Build kwargs for only provided fields
        kwargs = {}
        if monitoring_enabled is not None:
            kwargs["enabled"] = monitoring_enabled
        if monitoring_frequency is not None:
            kwargs["frequency"] = monitoring_frequency
        if alert_on_new_features is not None:
            kwargs["alert_on_new_features"] = alert_on_new_features
        if alert_on_removed_features is not None:
            kwargs["alert_on_removed_features"] = alert_on_removed_features
        if alert_on_new_competitors is not None:
            kwargs["alert_on_new_competitors"] = alert_on_new_competitors
        if min_feature_change_threshold is not None:
            kwargs["min_feature_change_threshold"] = min_feature_change_threshold
        if auto_generate_ideas is not None:
            kwargs["auto_generate_ideas"] = auto_generate_ideas
        if auto_idea_confidence_threshold is not None:
            kwargs["auto_idea_confidence_threshold"] = auto_idea_confidence_threshold
        if notify_product_owners is not None:
            kwargs["notify_product_owners"] = notify_product_owners

        if not kwargs:
            return {"error": "No configuration fields provided to update."}

        # The service always sets enabled/frequency, so carry forward current values
        existing = service.get_monitoring_config(product_id)
        effective_enabled = kwargs.pop("enabled", existing.monitoring_enabled if existing else False)
        effective_frequency = kwargs.pop("frequency", existing.monitoring_frequency if existing else "weekly")

        config = service.create_or_update_monitoring_config(
            product_id=product_id,
            enabled=effective_enabled,
            frequency=effective_frequency,
            **kwargs,
        )

        return {
            "product_id": product_id,
            "configured": True,
            "monitoring_enabled": config.monitoring_enabled,
            "monitoring_frequency": config.monitoring_frequency,
            "alert_on_new_features": config.alert_on_new_features,
            "alert_on_removed_features": config.alert_on_removed_features,
            "alert_on_new_competitors": config.alert_on_new_competitors,
            "min_feature_change_threshold": config.min_feature_change_threshold,
            "auto_generate_ideas": config.auto_generate_ideas,
            "auto_idea_confidence_threshold": config.auto_idea_confidence_threshold,
            "notify_product_owners": config.notify_product_owners,
            "message": "Monitoring config updated.",
        }
