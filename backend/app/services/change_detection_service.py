"""
Change Detection Service.

Computes structured diffs when competitive reports are re-run,
surfacing what actually changed between versions.
"""

from typing import Dict, Any, List, Optional


class ChangeDetectionService:
    """Computes structured diffs between report versions."""

    @staticmethod
    def compute_functional_report_diff(
        current_data: Dict[str, Any],
        previous_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two functional audit report versions.

        Args:
            current_data: Dict with functional_comparison, competitor_context,
                         gaps_deep_dive from the new report
            previous_data: Same structure from the previous report version

        Returns:
            Structured diff dict with new_features, removed_features,
            status_changes, positioning_changes, and summary.
        """
        curr_features = {
            f.get("competitor_feature_name", f.get("feature_name", "")): f
            for f in current_data.get("functional_comparison", [])
        }
        prev_features = {
            f.get("competitor_feature_name", f.get("feature_name", "")): f
            for f in previous_data.get("functional_comparison", [])
        }

        curr_names = set(curr_features.keys())
        prev_names = set(prev_features.keys())

        # New features (in current but not previous)
        new_features = [
            {
                "feature_name": name,
                "category": curr_features[name].get("feature_category", ""),
                "mapping_status": curr_features[name].get("mapping_status", ""),
            }
            for name in sorted(curr_names - prev_names)
        ]

        # Removed features (in previous but not current)
        removed_features = [
            {
                "feature_name": name,
                "category": prev_features[name].get("feature_category", ""),
            }
            for name in sorted(prev_names - curr_names)
        ]

        # Status changes (same feature, different mapping_status)
        status_changes = []
        for name in sorted(curr_names & prev_names):
            old_status = prev_features[name].get("mapping_status", "")
            new_status = curr_features[name].get("mapping_status", "")
            if old_status != new_status:
                status_changes.append({
                    "feature_name": name,
                    "old_status": old_status,
                    "new_status": new_status,
                })

        # Positioning changes
        positioning_changes = None
        curr_context = current_data.get("competitor_context", {})
        prev_context = previous_data.get("competitor_context", {})
        if curr_context and prev_context:
            old_pos = prev_context.get("positioning", "")
            new_pos = curr_context.get("positioning", "")
            if old_pos != new_pos and old_pos and new_pos:
                positioning_changes = {"old": old_pos, "new": new_pos}

        # Summary
        summary = ChangeDetectionService._build_functional_summary(
            new_features, removed_features, status_changes, positioning_changes
        )

        return {
            "new_features": new_features,
            "removed_features": removed_features,
            "status_changes": status_changes,
            "positioning_changes": positioning_changes,
            "summary": summary,
        }

    @staticmethod
    def compute_landscape_report_diff(
        current_data: Dict[str, Any],
        previous_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two landscape opportunity report versions.

        Args:
            current_data: Dict with feature_opportunities, high_impact_gaps
            previous_data: Same structure from the previous version

        Returns:
            Structured diff with new/removed opportunities, score changes,
            new/resolved gaps, and summary.
        """
        # Index opportunities by feature_name
        curr_opps = {
            o.get("feature_name", ""): o
            for o in current_data.get("feature_opportunities", [])
        }
        prev_opps = {
            o.get("feature_name", ""): o
            for o in previous_data.get("feature_opportunities", [])
        }

        curr_opp_names = set(curr_opps.keys())
        prev_opp_names = set(prev_opps.keys())

        new_opportunities = [
            {
                "name": name,
                "priority_score": curr_opps[name].get("priority_score", 0),
            }
            for name in sorted(curr_opp_names - prev_opp_names)
        ]

        removed_opportunities = [
            {
                "name": name,
                "was_priority_score": prev_opps[name].get("priority_score", 0),
            }
            for name in sorted(prev_opp_names - curr_opp_names)
        ]

        # Score changes for opportunities present in both
        score_changes = []
        for name in sorted(curr_opp_names & prev_opp_names):
            old_score = prev_opps[name].get("priority_score", 0) or 0
            new_score = curr_opps[name].get("priority_score", 0) or 0
            if abs(old_score - new_score) >= 1:  # Ignore trivial float diffs
                score_changes.append({
                    "name": name,
                    "old_score": old_score,
                    "new_score": new_score,
                    "direction": "up" if new_score > old_score else "down",
                })

        # High-impact gap changes
        curr_gaps = {
            g.get("feature_name", ""): g
            for g in current_data.get("high_impact_gaps", [])
        }
        prev_gaps = {
            g.get("feature_name", ""): g
            for g in previous_data.get("high_impact_gaps", [])
        }

        curr_gap_names = set(curr_gaps.keys())
        prev_gap_names = set(prev_gaps.keys())

        new_high_impact_gaps = [
            {
                "feature_name": name,
                "market_gravity": curr_gaps[name].get("market_gravity", ""),
            }
            for name in sorted(curr_gap_names - prev_gap_names)
        ]

        resolved_gaps = [
            {"feature_name": name}
            for name in sorted(prev_gap_names - curr_gap_names)
        ]

        summary = ChangeDetectionService._build_landscape_summary(
            new_opportunities, removed_opportunities, score_changes,
            new_high_impact_gaps, resolved_gaps
        )

        return {
            "new_opportunities": new_opportunities,
            "removed_opportunities": removed_opportunities,
            "score_changes": score_changes,
            "new_high_impact_gaps": new_high_impact_gaps,
            "resolved_gaps": resolved_gaps,
            "summary": summary,
        }

    @staticmethod
    def _build_functional_summary(
        new_features: List,
        removed_features: List,
        status_changes: List,
        positioning_changes: Optional[Dict],
    ) -> str:
        """Generate human-readable summary for functional report diff."""
        parts = []
        if new_features:
            parts.append(f"{len(new_features)} new feature(s) detected")
        if removed_features:
            parts.append(f"{len(removed_features)} feature(s) removed")
        if status_changes:
            gaps_closed = sum(
                1 for s in status_changes if s["old_status"] == "Gap"
            )
            new_gaps = sum(
                1 for s in status_changes if s["new_status"] == "Gap"
            )
            if gaps_closed:
                parts.append(f"{gaps_closed} gap(s) closed")
            if new_gaps:
                parts.append(f"{new_gaps} new gap(s)")
            other = len(status_changes) - gaps_closed - new_gaps
            if other > 0:
                parts.append(f"{other} other status change(s)")
        if positioning_changes:
            parts.append("positioning changed")

        return ", ".join(parts) if parts else "No significant changes"

    @staticmethod
    def _build_landscape_summary(
        new_opportunities: List,
        removed_opportunities: List,
        score_changes: List,
        new_gaps: List,
        resolved_gaps: List,
    ) -> str:
        """Generate human-readable summary for landscape report diff."""
        parts = []
        if new_opportunities:
            parts.append(f"{len(new_opportunities)} new opportunity/ies")
        if removed_opportunities:
            parts.append(f"{len(removed_opportunities)} removed opportunity/ies")
        if score_changes:
            ups = sum(1 for s in score_changes if s["direction"] == "up")
            downs = sum(1 for s in score_changes if s["direction"] == "down")
            if ups:
                parts.append(f"{ups} priority increase(s)")
            if downs:
                parts.append(f"{downs} priority decrease(s)")
        if new_gaps:
            parts.append(f"{len(new_gaps)} new high-impact gap(s)")
        if resolved_gaps:
            parts.append(f"{len(resolved_gaps)} resolved gap(s)")

        return ", ".join(parts) if parts else "No significant changes"
