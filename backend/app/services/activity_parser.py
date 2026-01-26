"""
Activity Parser Service for CRM activity data.

Parses both JSON and Markdown formats into a normalized internal structure
for processing by the Activity Insight Agent.

Supported formats:
- JSON: Programmatic exports from CRM APIs
- Markdown: Human-readable format for manual preparation
"""

import json
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ActivityRecord(BaseModel):
    """A single activity (call, email, meeting, note)."""
    type: str = "note"  # call, email, meeting, note
    timestamp: Optional[str] = None
    subject: Optional[str] = None
    body: str = ""
    direction: Optional[str] = None  # inbound, outbound
    duration_minutes: Optional[int] = None
    author: Optional[str] = None  # customer, agent, rep


class DealRecord(BaseModel):
    """A deal with its associated activities."""
    deal_id: Optional[str] = None
    deal_name: Optional[str] = None
    outcome: str = "unknown"  # won, lost, open, unknown
    close_date: Optional[str] = None
    competitor: Optional[str] = None
    deal_value: Optional[float] = None
    activities: list[ActivityRecord] = Field(default_factory=list)


class SupportTicketRecord(BaseModel):
    """A support ticket with its associated activities."""
    ticket_id: Optional[str] = None
    account_name: Optional[str] = None
    subject: Optional[str] = None
    activities: list[ActivityRecord] = Field(default_factory=list)


class ParsedActivityData(BaseModel):
    """Normalized structure for activity data from any format."""
    source: str = "manual"  # salesforce, hubspot, manual, etc.
    export_date: Optional[str] = None
    deals: list[DealRecord] = Field(default_factory=list)
    support_tickets: list[SupportTicketRecord] = Field(default_factory=list)


class ActivityParserService:
    """
    Parses CRM activity data from JSON or Markdown formats.

    Detects format automatically based on file extension or content,
    then normalizes to a common internal structure.
    """

    def parse(self, content: str, filename: str) -> ParsedActivityData:
        """
        Parse activity data from content string.

        Args:
            content: The file content as a string
            filename: The filename (used for format detection)

        Returns:
            ParsedActivityData with normalized structure
        """
        format_type = self._detect_format(content, filename)

        if format_type == "json":
            return self._parse_json(content)
        elif format_type == "markdown":
            return self._parse_markdown(content)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _detect_format(self, content: str, filename: str) -> str:
        """Detect file format from extension or content."""
        filename_lower = filename.lower()

        if filename_lower.endswith(".json"):
            return "json"
        elif filename_lower.endswith(".md") or filename_lower.endswith(".markdown"):
            return "markdown"

        # Try to detect from content
        content_stripped = content.strip()
        if content_stripped.startswith("{") or content_stripped.startswith("["):
            return "json"
        elif content_stripped.startswith("#"):
            return "markdown"

        # Default to JSON
        return "json"

    def _parse_json(self, content: str) -> ParsedActivityData:
        """Parse JSON format activity data."""
        data = json.loads(content)

        result = ParsedActivityData(
            source=data.get("source", "manual"),
            export_date=data.get("export_date")
        )

        # Parse deals
        for deal_data in data.get("deals", []):
            deal = DealRecord(
                deal_id=deal_data.get("deal_id"),
                deal_name=deal_data.get("deal_name"),
                outcome=deal_data.get("outcome", "unknown"),
                close_date=deal_data.get("close_date"),
                competitor=deal_data.get("competitor"),
                deal_value=deal_data.get("deal_value")
            )

            for activity_data in deal_data.get("activities", []):
                activity = ActivityRecord(
                    type=activity_data.get("type", "note"),
                    timestamp=activity_data.get("timestamp"),
                    subject=activity_data.get("subject"),
                    body=activity_data.get("body", ""),
                    direction=activity_data.get("direction"),
                    duration_minutes=activity_data.get("duration_minutes"),
                    author=activity_data.get("author")
                )
                deal.activities.append(activity)

            result.deals.append(deal)

        # Parse support activities
        for ticket_data in data.get("support_activities", data.get("support_tickets", [])):
            ticket = SupportTicketRecord(
                ticket_id=ticket_data.get("ticket_id"),
                account_name=ticket_data.get("account_name"),
                subject=ticket_data.get("subject")
            )

            for activity_data in ticket_data.get("activities", []):
                activity = ActivityRecord(
                    type=activity_data.get("type", "comment"),
                    timestamp=activity_data.get("timestamp"),
                    subject=activity_data.get("subject"),
                    body=activity_data.get("body", ""),
                    author=activity_data.get("author")
                )
                ticket.activities.append(activity)

            result.support_tickets.append(ticket)

        return result

    def _parse_markdown(self, content: str) -> ParsedActivityData:
        """
        Parse Markdown format activity data.

        Expected format:
        # Sales Activity Export - January 2025

        ## Deal: Acme Corp
        - **Outcome:** Lost
        - **Close Date:** 2025-01-15
        - **Competitor:** Competitor X
        - **Deal Value:** $50,000

        ### Activities

        #### Call - 2025-01-10 - Discovery Call
        Customer mentioned they need better Salesforce integration...

        #### Email - 2025-01-12 - Follow-up
        > "We really liked the demo, but..."

        ---

        ## Support Ticket: Ticket-123
        - **Account:** Beta Inc

        ### Activities

        #### Comment - 2025-01-12
        Customer: "We've been manually exporting..."
        """
        result = ParsedActivityData(source="manual")

        lines = content.split("\n")

        # Try to extract source from title
        title_match = re.match(r"^#\s+(.+?)\s*-?\s*(.+)?$", lines[0] if lines else "")
        if title_match:
            result.export_date = self._extract_date_from_text(title_match.group(0))

        current_deal: Optional[DealRecord] = None
        current_ticket: Optional[SupportTicketRecord] = None
        current_activity: Optional[ActivityRecord] = None
        in_activities_section = False
        activity_body_lines: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for deal header
            deal_match = re.match(r"^##\s+Deal:\s*(.+)$", stripped, re.IGNORECASE)
            if deal_match:
                # Save previous deal
                if current_deal:
                    self._finalize_activity(current_deal, current_activity, activity_body_lines)
                    result.deals.append(current_deal)

                current_deal = DealRecord(deal_name=deal_match.group(1).strip())
                current_ticket = None
                current_activity = None
                activity_body_lines = []
                in_activities_section = False
                continue

            # Check for support ticket header
            ticket_match = re.match(r"^##\s+Support\s+Ticket:\s*(.+)$", stripped, re.IGNORECASE)
            if ticket_match:
                # Save previous items
                if current_deal:
                    self._finalize_activity(current_deal, current_activity, activity_body_lines)
                    result.deals.append(current_deal)
                    current_deal = None
                if current_ticket:
                    self._finalize_activity(current_ticket, current_activity, activity_body_lines)
                    result.support_tickets.append(current_ticket)

                current_ticket = SupportTicketRecord(ticket_id=ticket_match.group(1).strip())
                current_activity = None
                activity_body_lines = []
                in_activities_section = False
                continue

            # Check for Activities section header
            if re.match(r"^###\s+Activities\s*$", stripped, re.IGNORECASE):
                in_activities_section = True
                continue

            # Check for activity header (#### Type - Date - Subject)
            activity_match = re.match(
                r"^####\s+(\w+)\s*-?\s*(\d{4}-\d{2}-\d{2})?\s*-?\s*(.+)?$",
                stripped,
                re.IGNORECASE
            )
            if activity_match and in_activities_section:
                # Save previous activity
                parent = current_deal or current_ticket
                if parent:
                    self._finalize_activity(parent, current_activity, activity_body_lines)

                current_activity = ActivityRecord(
                    type=activity_match.group(1).lower(),
                    timestamp=activity_match.group(2),
                    subject=activity_match.group(3).strip() if activity_match.group(3) else None
                )
                activity_body_lines = []
                continue

            # Parse deal/ticket metadata
            if current_deal and not in_activities_section:
                self._parse_metadata_line(stripped, current_deal)
            elif current_ticket and not in_activities_section:
                self._parse_ticket_metadata_line(stripped, current_ticket)

            # Collect activity body
            if current_activity and in_activities_section and stripped:
                # Skip horizontal rules
                if stripped.startswith("---"):
                    continue
                activity_body_lines.append(line)

        # Save final items
        if current_deal:
            self._finalize_activity(current_deal, current_activity, activity_body_lines)
            result.deals.append(current_deal)
        if current_ticket:
            self._finalize_activity(current_ticket, current_activity, activity_body_lines)
            result.support_tickets.append(current_ticket)

        return result

    def _parse_metadata_line(self, line: str, deal: DealRecord) -> None:
        """Parse a metadata line for a deal."""
        # Outcome
        match = re.match(r"^-?\s*\*?\*?Outcome:?\*?\*?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            deal.outcome = match.group(1).strip().lower()
            return

        # Close Date
        match = re.match(r"^-?\s*\*?\*?Close\s*Date:?\*?\*?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            deal.close_date = match.group(1).strip()
            return

        # Competitor
        match = re.match(r"^-?\s*\*?\*?Competitor:?\*?\*?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            deal.competitor = match.group(1).strip()
            return

        # Deal Value
        match = re.match(r"^-?\s*\*?\*?Deal\s*Value:?\*?\*?\s*:?\s*\$?([\d,]+).*$", line, re.IGNORECASE)
        if match:
            value_str = match.group(1).replace(",", "")
            try:
                deal.deal_value = float(value_str)
            except ValueError:
                pass
            return

        # Deal ID
        match = re.match(r"^-?\s*\*?\*?Deal\s*ID:?\*?\*?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            deal.deal_id = match.group(1).strip()
            return

    def _parse_ticket_metadata_line(self, line: str, ticket: SupportTicketRecord) -> None:
        """Parse a metadata line for a support ticket."""
        # Account
        match = re.match(r"^-?\s*\*?\*?Account:?\*?\*?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            ticket.account_name = match.group(1).strip()
            return

        # Subject
        match = re.match(r"^-?\s*\*?\*?Subject:?\*?\*?\s*:?\s*(.+)$", line, re.IGNORECASE)
        if match:
            ticket.subject = match.group(1).strip()
            return

    def _finalize_activity(
        self,
        parent: DealRecord | SupportTicketRecord,
        activity: Optional[ActivityRecord],
        body_lines: list[str]
    ) -> None:
        """Finalize an activity and add it to its parent."""
        if activity is None:
            return

        # Join body lines and clean up
        body = "\n".join(body_lines).strip()

        # Extract quoted text as customer voice
        quotes = re.findall(r'>\s*"?([^"\n]+)"?', body)
        if quotes:
            # Prioritize quoted content
            activity.body = " ".join(quotes)
        else:
            activity.body = body

        # Detect author from content
        if "customer:" in body.lower() or body.startswith(">"):
            activity.author = "customer"

        parent.activities.append(activity)

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Try to extract a date from text."""
        # Look for month-year pattern
        match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", text, re.IGNORECASE)
        if match:
            month_map = {
                "january": "01", "february": "02", "march": "03", "april": "04",
                "may": "05", "june": "06", "july": "07", "august": "08",
                "september": "09", "october": "10", "november": "11", "december": "12"
            }
            month = month_map.get(match.group(1).lower(), "01")
            year = match.group(2)
            return f"{year}-{month}-01"

        # Look for ISO date
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            return match.group(1)

        return None

    def get_format_type(self, filename: str) -> str:
        """Get the format type from filename."""
        filename_lower = filename.lower()
        if filename_lower.endswith(".json"):
            return "json"
        elif filename_lower.endswith(".md") or filename_lower.endswith(".markdown"):
            return "markdown"
        return "json"
