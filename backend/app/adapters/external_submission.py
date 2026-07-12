"""External Submission Adapter.

Normalizes ideas imported from external idea systems (Aha!, Canny, Jira
Product Discovery, spreadsheets) into the internal Idea shape, preserving
external provenance (external_id + external_source) so re-imports dedupe
and triage verdicts can be written back.

Deterministic by default — bulk imports must not silently burn LLM tokens.
Callers that want a title+description blob split into what/why/use_case run
the structuring step themselves before invoking this adapter (see the
ideas_import MCP tool's structure_with_llm flag).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.adapters.base import BaseSourceAdapter, NormalizedIdea
from app.models.idea import SourceType
from app.services.llm_service import LLMService


class ExternalSubmissionAdapter(BaseSourceAdapter):
    """Adapter for ideas that already exist in an external idea system.

    Field mapping (title/description required; the rest pass through when
    the external system has them):
    - title → title, description → what_description
    - why → why_description, use_case → use_case_description (default "")
    - category passthrough
    - external_id/external_source → provenance columns (unique per product)

    Metadata deliberately contains NONE of the authoritative trigger keys
    (competitor_name(s), job_id_key) — imported ideas are triaged like
    customer ideas, with the agent's judgment intact.
    """

    def __init__(self, db: Session, llm_service: Optional[LLMService] = None):
        self.db = db
        self.llm_service = llm_service  # unused; kept for registry symmetry

    def get_source_type(self) -> SourceType:
        return SourceType.EXTERNAL_SUBMISSION

    def get_required_fields(self) -> list:
        return ["product_id", "external_id", "external_source", "title", "description"]

    def validate_input(self, raw_input: Dict[str, Any]) -> bool:
        return all(
            str(raw_input.get(field) or "").strip()
            for field in self.get_required_fields()
        )

    def extract_metadata(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        if raw_input.get("url"):
            metadata["external_url"] = raw_input["url"]
        if raw_input.get("submitter"):
            metadata["submitter_label"] = raw_input["submitter"]
        if raw_input.get("vote_count") is not None:
            metadata["external_vote_count"] = int(raw_input["vote_count"])
        if raw_input.get("external_status"):
            metadata["external_status"] = raw_input["external_status"]
        return metadata

    def normalize(self, raw_input: Dict[str, Any]) -> NormalizedIdea:
        if not self.validate_input(raw_input):
            raise ValueError(
                "Invalid input: requires product_id, external_id, external_source, "
                "title, and description"
            )

        return NormalizedIdea(
            title=str(raw_input["title"]).strip()[:255],
            what_description=str(raw_input["description"]).strip(),
            why_description=str(raw_input.get("why") or "").strip(),
            use_case_description=str(raw_input.get("use_case") or "").strip(),
            source_type=SourceType.EXTERNAL_SUBMISSION,
            source_metadata=self.extract_metadata(raw_input),
            product_id=raw_input["product_id"],
            submitter_id=raw_input.get("submitter_id"),
            category=raw_input.get("category"),
            auto_categorized=False,
            external_id=str(raw_input["external_id"]).strip(),
            external_source=str(raw_input["external_source"]).strip(),
            raw_input=None,
        )
