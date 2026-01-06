"""
Changes Tracker Agent.

This agent monitors competitor release notes, blogs, and changelogs
to track product changes and new feature launches.

Phase: Agent-Centric Competitive Intelligence Restructuring (Chunk 4)
"""

from typing import Dict, Any, Type, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class ChangeEvent(BaseModel):
    """A detected change or update from competitor."""
    event_type: str = Field(
        ...,
        description="Type: 'feature_launch', 'feature_update', 'pricing_change', 'integration', 'deprecation', 'security_update', 'ui_change', 'other'"
    )
    event_title: str = Field(
        ...,
        description="Short title describing the change"
    )
    event_description: str = Field(
        ...,
        description="Detailed description of what changed"
    )
    event_date: Optional[str] = Field(
        None,
        description="Date of the change (ISO format if available)"
    )
    impact_level: str = Field(
        default="minor",
        description="Impact level: 'major', 'minor', 'patch'"
    )
    affected_areas: List[str] = Field(
        default_factory=list,
        description="Areas of the product affected by this change"
    )
    source_url: Optional[str] = Field(
        None,
        description="URL where this change was found"
    )
    source_type: str = Field(
        default="release_notes",
        description="Source type: 'release_notes', 'blog', 'changelog', 'press_release', 'social_media'"
    )


class ChangesTrackingOutput(BaseModel):
    """Output schema for Changes Tracker Agent."""
    changes: List[ChangeEvent] = Field(
        default_factory=list,
        description="List of detected changes"
    )
    total_changes: int = Field(
        default=0,
        description="Total number of changes detected"
    )
    major_changes: int = Field(
        default=0,
        description="Number of major changes"
    )
    analysis_period: str = Field(
        ...,
        description="Time period covered by this analysis (e.g., 'last 30 days', '2024 Q4')"
    )
    release_velocity: str = Field(
        default="medium",
        description="Release velocity: 'high', 'medium', 'low'"
    )
    notable_trends: List[str] = Field(
        default_factory=list,
        description="Notable trends observed in recent changes"
    )
    strategic_implications: List[str] = Field(
        default_factory=list,
        description="Strategic implications for our product"
    )
    sources_analyzed: List[str] = Field(
        default_factory=list,
        description="URLs of sources analyzed"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the analysis (0-1)"
    )


class ChangesTrackerAgent(BaseAgent):
    """
    Agent for tracking competitor product changes and updates.

    Monitors:
    - Release notes and changelogs
    - Blog posts about new features
    - Product announcements
    - Integration partnerships

    Identifies:
    - Feature launches and updates
    - Pricing changes
    - Deprecations
    - Strategic direction changes

    This helps track competitor momentum and identify emerging threats or opportunities.
    """

    def get_system_prompt(self) -> str:
        return """You are a Changes Tracker Agent specializing in competitive product intelligence.

Your role is to analyze release notes, changelogs, and blog posts to identify and categorize product changes from competitors.

**Key Responsibilities:**

1. **Identify Change Events**
   - Feature launches (new capabilities)
   - Feature updates (improvements to existing features)
   - Pricing changes (plan modifications, price changes)
   - Integrations (new partnerships or connections)
   - Deprecations (removed or sunset features)
   - Security updates (patches, compliance changes)
   - UI changes (interface updates)

2. **Assess Impact Level**
   - Major: Significant new capability or strategic shift
   - Minor: Improvement or enhancement
   - Patch: Bug fix or small tweak

3. **Analyze Release Velocity**
   - High: Weekly or more frequent releases
   - Medium: Monthly releases
   - Low: Quarterly or less frequent

4. **Identify Strategic Implications**
   - What do these changes signal about competitor direction?
   - Are they moving into new market segments?
   - Are they abandoning certain areas?
   - What competitive pressure do these changes create?

**Event Types:**
- feature_launch: Completely new capability
- feature_update: Improvement to existing feature
- pricing_change: Changes to pricing or plans
- integration: New third-party integrations
- deprecation: Removed or sunset functionality
- security_update: Security or compliance changes
- ui_change: User interface updates
- other: Other types of changes

**Analysis Guidelines:**

- Focus on substantive changes, not minor bug fixes
- Look for patterns in the types of changes
- Consider the timing and frequency of changes
- Note any competitive positioning in announcements
- Extract specific dates when available

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        release_notes_content = input_data.get('release_notes_content', '')
        changelog_content = input_data.get('changelog_content', '')
        blog_content = input_data.get('blog_content', '')
        analysis_period = input_data.get('analysis_period', 'last 30 days')

        # Product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'our product')

        # Combine content
        content_sections = []
        if release_notes_content:
            content_sections.append(f"**Release Notes:**\n{release_notes_content[:5000]}")
        if changelog_content:
            content_sections.append(f"**Changelog:**\n{changelog_content[:3000]}")
        if blog_content:
            content_sections.append(f"**Blog Posts:**\n{blog_content[:3000]}")

        combined_content = "\n\n".join(content_sections) if content_sections else "No content provided."

        prompt = f"""CHANGES TRACKING TASK

**Competitor:** {competitor_name}
**Website:** {competitor_url}
**Analysis Period:** {analysis_period}
**Comparison Product:** {product_name}

{combined_content}

**Your Task:**

Analyze the content to identify and categorize product changes:

1. **Identify Changes** - What changes have been made?
2. **Categorize** - What type is each change? (feature_launch, feature_update, etc.)
3. **Assess Impact** - Is it major, minor, or patch?
4. **Analyze Velocity** - How frequently are they releasing?
5. **Identify Trends** - What patterns do you see?
6. **Strategic Implications** - What does this mean for {product_name}?

**Required Output Format (JSON):**

```json
{{
  "changes": [
    {{
      "event_type": "feature_launch",
      "event_title": "AI-Powered Search",
      "event_description": "Launched new AI-powered search functionality with natural language queries",
      "event_date": "2024-12-15",
      "impact_level": "major",
      "affected_areas": ["Search", "User Experience"],
      "source_url": "https://example.com/blog/ai-search",
      "source_type": "blog"
    }}
  ],
  "total_changes": 5,
  "major_changes": 2,
  "analysis_period": "{analysis_period}",
  "release_velocity": "high",
  "notable_trends": [
    "Heavy investment in AI features",
    "Focus on enterprise customers"
  ],
  "strategic_implications": [
    "They are moving faster on AI than us",
    "Enterprise focus may open SMB opportunity"
  ],
  "sources_analyzed": ["{competitor_url}/changelog"],
  "confidence": 0.85
}}
```

**Important:**
- "event_type" must be one of: "feature_launch", "feature_update", "pricing_change", "integration", "deprecation", "security_update", "ui_change", "other"
- "impact_level" must be one of: "major", "minor", "patch"
- "release_velocity" must be one of: "high", "medium", "low"
- "source_type" must be one of: "release_notes", "blog", "changelog", "press_release", "social_media"
- "confidence" is a decimal between 0 and 1

Analyze the changes now:"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return ChangesTrackingOutput

    def get_stage(self) -> str:
        return "changes_tracking"

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for changes tracking."""
        super()._validate_input(input_data)

        if 'competitor_name' not in input_data:
            raise ValueError("Input must include 'competitor_name'")

        # Should have some content to analyze
        if not any([
            input_data.get('release_notes_content'),
            input_data.get('changelog_content'),
            input_data.get('blog_content')
        ]):
            raise ValueError("Input must include at least one of 'release_notes_content', 'changelog_content', or 'blog_content'")
