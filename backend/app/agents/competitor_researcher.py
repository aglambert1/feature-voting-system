"""
Competitor Research Agents for discovering and analyzing competitors.

This module provides two AI agents:
1. CompetitorResearcherAgent - Discovers 10-15 competing products via web research
2. DifferentialAnalysisAgent - Compares current discoveries with previous analysis
"""

from typing import Dict, Any, Type, List
from pydantic import BaseModel, Field, HttpUrl
from app.agents.base_agent import BaseAgent


class CompetitorResult(BaseModel):
    """Single competitor discovery result"""
    name: str = Field(..., description="Competitor product name", validation_alias="product_name")
    url: HttpUrl = Field(..., description="Primary website URL", validation_alias="website")
    summary: str = Field(..., description="2-3 sentence summary of what they do")
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How directly they compete (0.0-1.0)"
    )

    class Config:
        populate_by_name = True


class CompetitorResearchOutput(BaseModel):
    """Output schema for Competitor Researcher Agent"""
    competitors: List[CompetitorResult] = Field(
        ...,
        description="List of discovered competitors",
        min_items=5,
        max_items=20
    )
    research_summary: str = Field(
        ...,
        description="Brief summary of competitive landscape"
    )


class CompetitorResearcherAgent(BaseAgent):
    """
    Discovers competing products through web research.

    Uses product information to search for and identify competitors.
    Returns ranked list of competitors with relevance scores.
    """

    def get_system_prompt(self) -> str:
        return """You are a Competitor Research agent specializing in market intelligence.

Your role is to discover competing products based on a target product's description.

You must:
1. Identify direct competitors (products serving the same market/needs)
2. Prioritize active, established products over defunct or tangential ones
3. Provide accurate URLs and concise summaries
4. Score relevance objectively (1.0 = direct competitor, 0.5 = adjacent market)

Focus on quality over quantity. Return 10-15 most relevant competitors.

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get('product_name', '')
        product_category = input_data.get('product_category', '')
        core_features = input_data.get('core_features', [])
        target_users = input_data.get('target_users', '')
        search_keywords = input_data.get('competitor_search_keywords', [])

        prompt = f"""Research and identify competing products for the following:

**Target Product:** {product_name}
**Category:** {product_category}
**Key Features:** {', '.join(core_features)}
**Target Users:** {target_users}
**Search Keywords:** {', '.join(search_keywords)}

Your task:
1. Use web search to discover 10-15 competing products
2. For each competitor, provide the required information
3. Also provide a brief research_summary describing the competitive landscape

Guidelines:
- Focus on DIRECT competitors (same market, same user needs)
- Prefer established, active products
- Include variety (large players and emerging competitors)
- Verify URLs are valid and current
- Be objective with relevance scores (1.0 = direct competitor, 0.5 = adjacent market)

CRITICAL: You MUST return results in this EXACT JSON format with ALL required fields:
{{
  "competitors": [
    {{
      "name": "Competitor Product Name",
      "url": "https://www.example.com",
      "summary": "2-3 sentences explaining what this competitor does and how it competes",
      "relevance_score": 0.9
    }}
  ],
  "research_summary": "2-3 sentences describing the overall competitive landscape"
}}

REQUIRED FIELDS (all must be included):
- name: The competitor's product/company name
- url: Full website URL (must start with http:// or https://)
- summary: 2-3 sentence description
- relevance_score: Number between 0.0 and 1.0
"""
        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return CompetitorResearchOutput

    def get_stage(self) -> str:
        return "competitor_discovery"


class DifferentialAnalysisAgent(BaseAgent):
    """
    Compares new competitor discoveries with previous analysis.

    Identifies:
    - NEW: Competitors not in previous analysis
    - CONTINUING: Competitors in both analyses
    - DISAPPEARED: Previous competitors not found currently
    """

    def get_system_prompt(self) -> str:
        return """You are a Differential Analysis agent specializing in competitive intelligence.

Your role is to compare new competitor discovery results with a previous analysis to identify changes in the competitive landscape.

You must:
1. Match competitors between current and previous analyses (by name/URL similarity)
2. Categorize each competitor as: NEW, CONTINUING, or DISAPPEARED
3. Assess significance of changes (how important is this shift?)
4. Provide clear explanations for status changes

Be analytical and highlight truly meaningful competitive shifts, not minor variations.

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        current_competitors = input_data.get('current_competitors', [])
        previous_competitors = input_data.get('previous_competitors', [])
        product_name = input_data.get('product_name', '')

        prompt = f"""Compare competitor analyses for: {product_name}

**Current Analysis:**
{self._format_competitors(current_competitors)}

**Previous Analysis:**
{self._format_competitors(previous_competitors)}

Your task:
1. Match competitors between the two lists (by name and URL)
2. For each current competitor, determine:
   - status: "new" (wasn't in previous), "continuing" (in both), or "disappeared" (only in previous)
   - status_explanation: Brief reason for the status (e.g., "New market entrant", "Still active competitor")
   - significance: "low", "medium", or "high" (how important is this change?)
   - previous_competitor_match: If continuing, which previous competitor it matches

3. Provide summary statistics:
   - new_count: Number of new competitors
   - continuing_count: Number of continuing competitors
   - disappeared_count: Number of disappeared competitors
   - significant_changes: List of 2-4 brief descriptions of important changes

Return JSON format:
{{
  "competitors": [
    {{
      "name": "...",
      "url": "...",
      "summary": "...",
      "relevance_score": 0.9,
      "status": "new"|"continuing"|"disappeared",
      "status_explanation": "...",
      "significance": "low"|"medium"|"high",
      "previous_competitor_id": "uuid or null"
    }}
  ],
  "summary": {{
    "new_count": 0,
    "continuing_count": 0,
    "disappeared_count": 0,
    "significant_changes": ["..."]
  }}
}}
"""
        return prompt

    def _format_competitors(self, competitors: List[Dict]) -> str:
        """Format competitor list for prompt"""
        if not competitors:
            return "(None)"

        lines = []
        for comp in competitors:
            lines.append(f"- {comp.get('name', 'Unknown')}: {comp.get('url', 'N/A')}")
        return '\n'.join(lines)

    def get_output_schema(self) -> Type[BaseModel]:
        class DifferentialOutput(BaseModel):
            class CompetitorWithStatus(BaseModel):
                name: str
                url: str
                summary: str
                relevance_score: float
                status: str = Field(..., pattern="^(new|continuing|disappeared)$")
                status_explanation: str
                significance: str = Field(..., pattern="^(low|medium|high)$")
                previous_competitor_id: str | None = None

            class Summary(BaseModel):
                new_count: int
                continuing_count: int
                disappeared_count: int
                significant_changes: List[str]

            competitors: List[CompetitorWithStatus]
            summary: Summary

        return DifferentialOutput

    def get_stage(self) -> str:
        return "differential_analysis"
