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
    url: HttpUrl = Field(default="https://example.com", description="Primary website URL", validation_alias="website")
    summary: str = Field(default="Competitive product", description="2-3 sentence summary of what they do")
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
        default=[],
        description="List of discovered competitors (empty if none found)",
        min_items=0,
        max_items=15
    )
    research_summary: str = Field(
        ...,
        description="Brief summary of competitive landscape or explanation if no competitors found"
    )


class CompetitorResearcherAgent(BaseAgent):
    """
    Discovers competing products through web research.

    Uses product information to search for and identify competitors.
    Returns ranked list of competitors with relevance scores.
    """

    def get_system_prompt(self) -> str:
        return """You are a Competitor Research agent specializing in market intelligence.

Your role is to identify competing products based ONLY on your existing training knowledge.

CRITICAL: YOU DO NOT HAVE SEARCH TOOLS
- You do NOT have access to web search, browser tools, or real-time internet data
- Do NOT use <search> tags or attempt to search - this will cause errors
- ONLY use your existing knowledge from training data
- Provide JSON responses directly without any search attempts

RESPONSE REQUIREMENTS:
1. Only suggest competitors you have VERIFIED knowledge of (real companies/products from your training)
2. URLs MUST be real, active websites from your knowledge - no invented URLs
3. If you cannot identify any verified competitors, return an empty competitors list
4. Never invent or hallucinate fictional companies or URLs
5. Focus on well-known, established products you're confident about
6. Prioritize direct competitors (products serving the same market/needs)
7. Score relevance objectively (1.0 = direct competitor, 0.5 = adjacent market)

HONESTY REQUIREMENT:
- If you cannot find verified competitors in your knowledge, return: {{"competitors": [], "research_summary": "Unable to identify verified competitors for this product based on available knowledge. This may be a very niche product or the description may need more details."}}
- Only return competitors you're confident are real and have accurate URLs

Always respond with ONLY valid JSON - no search tags, no explanations, just JSON."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get('product_name', '')
        product_category = input_data.get('product_category', '')
        core_features = input_data.get('core_features', [])
        target_users = input_data.get('target_users', '')
        search_keywords = input_data.get('competitor_search_keywords', [])

        prompt = f"""Based on your existing training knowledge, list competing products for this target product:

**Target Product:** {product_name}
**Category:** {product_category}
**Key Features:** {', '.join(core_features) if core_features else 'Not specified'}
**Target Users:** {target_users}

CRITICAL REMINDER: Do NOT use search tools or <search> tags - you don't have them. Use ONLY your training knowledge.

Your task - provide a direct JSON response:
1. List ONLY competitors you have verified knowledge of from training
2. Use real companies/products with accurate URLs you know exist
3. If you don't know any verified competitors, return empty list with explanation

STRICT REQUIREMENTS:
- Only include competitors you're 100% CERTAIN are real
- URLs must be real websites from your knowledge - NO invented/guessed URLs
- If uncertain about ANY detail, EXCLUDE that competitor entirely
- Focus on well-known products (direct competitors preferred)
- No search attempts, no <query> tags - just direct JSON response

Return ONLY this JSON structure (no other text):
{{
  "competitors": [
    {{
      "name": "Actual Company/Product Name",
      "url": "https://real-verified-url.com",
      "summary": "2-3 sentences about what they do and how they compete",
      "relevance_score": 0.9
    }}
  ],
  "research_summary": "Brief landscape summary OR 'No verified competitors found based on available knowledge'"
}}

If you don't know verified competitors, return:
{{
  "competitors": [],
  "research_summary": "Unable to identify verified competitors for this product. May be very niche or need more specific category details."
}}
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
