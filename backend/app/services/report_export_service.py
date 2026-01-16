"""
Report Export Service for competitive analysis reports.

Handles automatic export of reports to the filesystem for historical preservation.
Reports are saved with timestamps to maintain history across scheduled runs.

Export folder structure:
    data/competitive_reports/{product_id}/{timestamp}/
        {competitor_name}_functional_audit.md
        landscape_synthesis.md
        feature_opportunities.json
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.models.competitive_reports import (
    CompetitorFunctionalReport,
    LandscapeOpportunityReport
)
from app.agents.functional_audit_agent import generate_markdown_report as generate_functional_md
from app.agents.landscape_synthesizer_agent import generate_markdown_report as generate_landscape_md
from app.schemas.competitive_reports import (
    FunctionalAuditOutput,
    LandscapeSynthesisOutput,
    CompetitorContext,
    FunctionalComparison,
    GapDeepDive,
    TechnicalConstraints,
    FeatureClusterEntry,
    FeatureOpportunity,
    HighImpactGap
)


class ReportExportService:
    """
    Service for exporting competitive analysis reports to the filesystem.

    Reports are saved with timestamps to preserve history across scheduled runs.
    This allows audit trails and comparison of analysis over time.

    Usage:
        service = ReportExportService()

        # Export a single competitor report
        path = service.export_functional_report(report, competitor_name)

        # Export all reports for a product run
        paths = service.export_analysis_run(
            product_id=123,
            product_name="My Product",
            functional_reports=reports,
            landscape_report=landscape
        )
    """

    def __init__(self, base_path: str = None):
        """
        Initialize the export service.

        Args:
            base_path: Base directory for exports. Defaults to backend/data/competitive_reports/
        """
        if base_path is None:
            # Default to data/competitive_reports relative to backend
            backend_root = Path(__file__).parent.parent.parent
            base_path = backend_root / "data" / "competitive_reports"

        self.base_path = Path(base_path)
        self._ensure_directory_exists(self.base_path)

    def _ensure_directory_exists(self, path: Path) -> None:
        """Create directory if it doesn't exist."""
        path.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string for use in a filename.

        Replaces spaces and special characters with underscores.
        """
        # Replace spaces and common special characters
        sanitized = re.sub(r'[^\w\-]', '_', name)
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized.lower()

    def _get_timestamp_folder(self) -> str:
        """Generate a timestamp string for folder naming."""
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def _get_product_folder(self, product_id: int, timestamp: str = None) -> Path:
        """
        Get the folder path for a product's exports.

        Args:
            product_id: Product ID
            timestamp: Optional timestamp string (generates new one if None)

        Returns:
            Path to the export folder
        """
        if timestamp is None:
            timestamp = self._get_timestamp_folder()

        folder = self.base_path / str(product_id) / timestamp
        self._ensure_directory_exists(folder)
        return folder

    def export_functional_report(
        self,
        report: CompetitorFunctionalReport,
        competitor_name: str,
        product_id: int,
        timestamp: str = None
    ) -> str:
        """
        Export a single functional audit report as markdown.

        Args:
            report: CompetitorFunctionalReport model instance
            competitor_name: Name of the competitor
            product_id: Product ID
            timestamp: Optional timestamp (for grouping with other exports)

        Returns:
            Path to the exported file
        """
        folder = self._get_product_folder(product_id, timestamp)
        filename = f"{self._sanitize_filename(competitor_name)}_functional_audit.md"
        filepath = folder / filename

        # Generate markdown content
        if report.report_content_md:
            # Use pre-generated markdown if available
            content = report.report_content_md
        else:
            # Generate from structured data
            content = self._generate_functional_markdown(report, competitor_name)

        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(filepath)

    def export_landscape_report(
        self,
        report: LandscapeOpportunityReport,
        product_name: str,
        product_id: int,
        competitor_count: int,
        timestamp: str = None
    ) -> str:
        """
        Export a landscape synthesis report as markdown.

        Args:
            report: LandscapeOpportunityReport model instance
            product_name: Name of our product
            product_id: Product ID
            competitor_count: Number of competitors in the analysis
            timestamp: Optional timestamp (for grouping with other exports)

        Returns:
            Path to the exported file
        """
        folder = self._get_product_folder(product_id, timestamp)
        filename = "landscape_synthesis.md"
        filepath = folder / filename

        # Generate markdown content
        if report.report_content_md:
            content = report.report_content_md
        else:
            content = self._generate_landscape_markdown(report, product_name, competitor_count)

        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(filepath)

    def export_feature_opportunities(
        self,
        report: LandscapeOpportunityReport,
        product_name: str,
        product_id: int,
        timestamp: str = None
    ) -> str:
        """
        Export feature opportunities as portable JSON.

        Args:
            report: LandscapeOpportunityReport model instance
            product_name: Name of our product
            product_id: Product ID
            timestamp: Optional timestamp (for grouping with other exports)

        Returns:
            Path to the exported file
        """
        folder = self._get_product_folder(product_id, timestamp)
        filename = "feature_opportunities.json"
        filepath = folder / filename

        # Build export structure
        export_data = report.get_portable_export(product_name)

        # Write to file with pretty formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return str(filepath)

    def export_analysis_run(
        self,
        product_id: int,
        product_name: str,
        functional_reports: List[tuple],  # List of (CompetitorFunctionalReport, competitor_name)
        landscape_report: Optional[LandscapeOpportunityReport] = None
    ) -> Dict[str, Any]:
        """
        Export all reports from a single analysis run.

        Creates a timestamped folder with all reports from this run.

        Args:
            product_id: Product ID
            product_name: Name of our product
            functional_reports: List of (report, competitor_name) tuples
            landscape_report: Optional landscape synthesis report

        Returns:
            Dict with export paths and summary:
            {
                'timestamp': str,
                'folder': str,
                'functional_reports': [str, ...],
                'landscape_report': str or None,
                'feature_opportunities': str or None,
                'total_files': int
            }
        """
        timestamp = self._get_timestamp_folder()
        folder = self._get_product_folder(product_id, timestamp)

        result = {
            'timestamp': timestamp,
            'folder': str(folder),
            'functional_reports': [],
            'landscape_report': None,
            'feature_opportunities': None,
            'total_files': 0
        }

        # Export functional reports
        for report, competitor_name in functional_reports:
            try:
                path = self.export_functional_report(
                    report=report,
                    competitor_name=competitor_name,
                    product_id=product_id,
                    timestamp=timestamp
                )
                result['functional_reports'].append(path)
                result['total_files'] += 1
            except Exception as e:
                print(f"[ReportExportService] Error exporting {competitor_name}: {e}")

        # Export landscape report and feature opportunities
        if landscape_report:
            try:
                path = self.export_landscape_report(
                    report=landscape_report,
                    product_name=product_name,
                    product_id=product_id,
                    competitor_count=len(functional_reports),
                    timestamp=timestamp
                )
                result['landscape_report'] = path
                result['total_files'] += 1
            except Exception as e:
                print(f"[ReportExportService] Error exporting landscape: {e}")

            try:
                path = self.export_feature_opportunities(
                    report=landscape_report,
                    product_name=product_name,
                    product_id=product_id,
                    timestamp=timestamp
                )
                result['feature_opportunities'] = path
                result['total_files'] += 1
            except Exception as e:
                print(f"[ReportExportService] Error exporting opportunities: {e}")

        # Write a summary file
        self._write_summary(folder, result, product_name)

        return result

    def _write_summary(self, folder: Path, result: Dict[str, Any], product_name: str) -> None:
        """Write a summary.json file for the export run."""
        summary = {
            'product_name': product_name,
            'timestamp': result['timestamp'],
            'exported_at': datetime.utcnow().isoformat() + 'Z',
            'files': {
                'functional_reports': len(result['functional_reports']),
                'landscape_report': 1 if result['landscape_report'] else 0,
                'feature_opportunities': 1 if result['feature_opportunities'] else 0,
            },
            'total_files': result['total_files']
        }

        filepath = folder / "summary.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

    def _generate_functional_markdown(
        self,
        report: CompetitorFunctionalReport,
        competitor_name: str
    ) -> str:
        """Generate markdown from structured report data."""
        # Convert stored JSON to Pydantic models for the generator
        try:
            context_data = report.competitor_context or {}
            comparison_data = report.functional_comparison or []
            gaps_data = report.gaps_deep_dive or []
            constraints_data = report.technical_constraints or {}

            output = FunctionalAuditOutput(
                competitor_context=CompetitorContext(**context_data) if context_data else CompetitorContext(
                    positioning="Unknown",
                    core_differentiation="Unknown",
                    target_customer="Unknown"
                ),
                functional_comparison=[
                    FunctionalComparison(**c) for c in comparison_data
                ],
                gaps_deep_dive=[
                    GapDeepDive(**g) for g in gaps_data
                ],
                technical_constraints=TechnicalConstraints(**constraints_data) if constraints_data else TechnicalConstraints()
            )

            return generate_functional_md(competitor_name, output)
        except Exception as e:
            # Fallback to simple format if conversion fails
            print(f"[ReportExportService] Error generating functional markdown: {e}")
            return f"# Functional Audit: {competitor_name}\n\n*Error generating report*"

    def _generate_landscape_markdown(
        self,
        report: LandscapeOpportunityReport,
        product_name: str,
        competitor_count: int
    ) -> str:
        """Generate markdown from structured report data."""
        try:
            matrix_data = report.feature_cluster_matrix or []
            opportunities_data = report.feature_opportunities or []
            gaps_data = report.high_impact_gaps or []

            output = LandscapeSynthesisOutput(
                feature_cluster_matrix=[
                    FeatureClusterEntry(**m) for m in matrix_data
                ],
                feature_opportunities=[
                    FeatureOpportunity(**o) for o in opportunities_data
                ],
                high_impact_gaps=[
                    HighImpactGap(**g) for g in gaps_data
                ]
            )

            return generate_landscape_md(product_name, output, competitor_count)
        except Exception as e:
            print(f"[ReportExportService] Error generating landscape markdown: {e}")
            return f"# Landscape Analysis: {product_name}\n\n*Error generating report*"

    def get_export_history(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Get list of previous export runs for a product.

        Args:
            product_id: Product ID

        Returns:
            List of export run summaries, newest first
        """
        product_folder = self.base_path / str(product_id)

        if not product_folder.exists():
            return []

        runs = []
        for timestamp_folder in sorted(product_folder.iterdir(), reverse=True):
            if timestamp_folder.is_dir():
                summary_file = timestamp_folder / "summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r') as f:
                            summary = json.load(f)
                            summary['folder'] = str(timestamp_folder)
                            runs.append(summary)
                    except Exception:
                        # Add basic info if summary can't be read
                        runs.append({
                            'timestamp': timestamp_folder.name,
                            'folder': str(timestamp_folder)
                        })

        return runs


# Global singleton instance
_export_service: Optional[ReportExportService] = None


def get_report_export_service(base_path: str = None) -> ReportExportService:
    """
    Get or create the global ReportExportService instance.

    Args:
        base_path: Base directory for exports (only used on first call)

    Returns:
        ReportExportService instance
    """
    global _export_service
    if _export_service is None:
        _export_service = ReportExportService(base_path=base_path)
    return _export_service
