"""
Competitor Research Agents for discovering and analyzing competitors.

This module provides two AI agents:
1. CompetitorResearcherAgent - Discovers 10-15 competing products via web research
2. DifferentialAnalysisAgent - Compares current discoveries with previous analysis
"""

from typing import Dict, Any, Type, List
from pydantic import BaseModel, Field, HttpUrl
from app.agents.base_agent import BaseAgent
from app.services.search_service import get_search_service


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
    Supports hybrid approach: training knowledge + web search.
    """

    def __init__(self, *args, **kwargs):
        """Initialize agent with search service."""
        super().__init__(*args, **kwargs)
        self.search_service = get_search_service()

    def get_tools(self) -> List[Dict[str, Any]]:
        """Provide web search tool if available."""
        if self.search_service.is_available():
            return [self.search_service.get_tool_definition()]
        return []

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute web search tool."""
        if tool_name == "web_search":
            query = tool_input.get("query", "")
            max_results = tool_input.get("max_results", 10)

            print(f"[CompetitorResearcher] Searching web for: {query}")
            results = self.search_service.search(query, max_results)

            # Format results for Claude
            if not results:
                return "No search results found for this query."

            formatted = []
            for i, result in enumerate(results, 1):
                formatted.append(
                    f"{i}. **{result.get('title', 'Untitled')}**\n"
                    f"   URL: {result.get('url', 'N/A')}\n"
                    f"   {result.get('snippet', 'No description available')}"
                )

            return "\n\n".join(formatted)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def get_system_prompt(self) -> str:
        has_search = self.search_service.is_available()

        if has_search:
            return """You are a Competitor Research agent specializing in market intelligence.

Your role is to identify competing products using a HYBRID APPROACH:
1. Start with your existing training knowledge for well-known competitors
2. Use the web_search tool to find current/emerging competitors and verify information

SEARCH STRATEGY:
- Use targeted searches like "[product category] competitors", "[product type] alternatives"
- Search for specific features or use cases to find similar products
- Verify URLs and company information through search results
- Combine knowledge from multiple searches for comprehensive results

RESPONSE REQUIREMENTS:
1. Aim for 5-10 high-quality competitors (direct competitors preferred)
2. All URLs must be real, verified from search results or training knowledge
3. Prioritize direct competitors (serve the same market/needs) over adjacent products
4. Score relevance objectively (1.0 = direct competitor, 0.5 = adjacent market)
5. Provide clear, accurate summaries based on search results
6. If searches return no relevant results, rely on training knowledge
7. If neither search nor knowledge helps, return empty list with explanation

IMPORTANT:
- Never invent or hallucinate companies, URLs, or information
- Only include competitors you can verify through search or training knowledge
- Return ONLY valid JSON - no markdown, no extra text

Always respond with valid JSON matching the schema."""
        else:
            # Fallback to knowledge-only mode if search unavailable
            return """You are a Competitor Research agent specializing in market intelligence.

Your role is to identify competing products based on your existing training knowledge.

IMPORTANT: Web search is currently unavailable, so use ONLY your training knowledge.

RESPONSE REQUIREMENTS:
1. Only suggest competitors you have VERIFIED knowledge of (real companies/products from your training)
2. URLs MUST be real, active websites from your knowledge - no invented URLs
3. If you cannot identify any verified competitors, return an empty competitors list
4. Never invent or hallucinate fictional companies or URLs
5. Focus on well-known, established products you're confident about
6. Prioritize direct competitors (products serving the same market/needs)
7. Score relevance objectively (1.0 = direct competitor, 0.5 = adjacent market)

HONESTY REQUIREMENT:
- If you cannot find verified competitors in your knowledge, return: {{"competitors": [], "research_summary": "Unable to identify verified competitors for this product based on available knowledge. Web search is currently unavailable."}}
- Only return competitors you're confident are real and have accurate URLs

Always respond with ONLY valid JSON - no explanations, just JSON."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get('product_name', '')
        product_category = input_data.get('product_category', '')
        core_features = input_data.get('core_features', [])
        target_users = input_data.get('target_users', '')
        search_keywords = input_data.get('competitor_search_keywords', [])

        has_search = self.search_service.is_available()

        if has_search:
            # Hybrid prompt - encourage search use
            prompt = f"""Find competing products for this target product:

**Target Product:** {product_name}
**Category:** {product_category}
**Key Features:** {', '.join(core_features) if core_features else 'Not specified'}
**Target Users:** {target_users}
**Suggested Keywords:** {', '.join(search_keywords) if search_keywords else 'Not provided'}

YOUR TASK:
1. **Start with knowledge**: Think of well-known competitors you know from training
2. **Use web search**: Search for "{product_category} competitors", "{product_category} alternatives", or similar queries
3. **Verify & compile**: Combine knowledge + search results into a comprehensive list
4. **Aim for quality**: 5-10 direct competitors preferred over a long list

SEARCH SUGGESTIONS:
- "{product_category} competitors"
- "{product_category} alternatives to {product_name}"
- "best {product_category} tools"
- Feature-specific searches if relevant (e.g., "{', '.join(core_features[:2]) if core_features else 'features'}")

REQUIREMENTS:
- All URLs must be real and verifiable (from search results or training knowledge)
- Prioritize DIRECT competitors (same market, same needs) - score 0.8-1.0
- Include adjacent products only if highly relevant - score 0.5-0.7
- Provide clear, accurate summaries based on what you learn
- If searches return nothing useful, rely on training knowledge
- If neither helps, return empty list with honest explanation

Return JSON format:
{{
  "competitors": [
    {{
      "name": "Company/Product Name",
      "url": "https://verified-url.com",
      "summary": "2-3 sentences about what they do and competitive positioning",
      "relevance_score": 0.9
    }}
  ],
  "research_summary": "Brief summary of competitive landscape"
}}"""
        else:
            # Knowledge-only prompt
            prompt = f"""Based on your training knowledge, list competing products for this target product:

**Target Product:** {product_name}
**Category:** {product_category}
**Key Features:** {', '.join(core_features) if core_features else 'Not specified'}
**Target Users:** {target_users}

IMPORTANT: Web search is unavailable - use ONLY your training knowledge.

YOUR TASK:
1. List ONLY competitors you have verified knowledge of from training
2. Use real companies/products with accurate URLs you're confident about
3. If you don't know verified competitors, return empty list with explanation

REQUIREMENTS:
- Only include competitors you're 100% CERTAIN are real
- URLs must be real websites from your knowledge - NO invented URLs
- If uncertain about ANY detail, EXCLUDE that competitor entirely
- Focus on well-known products (direct competitors preferred)

Return JSON format:
{{
  "competitors": [
    {{
      "name": "Actual Company/Product Name",
      "url": "https://real-verified-url.com",
      "summary": "2-3 sentences about what they do",
      "relevance_score": 0.9
    }}
  ],
  "research_summary": "Brief landscape summary OR 'Unable to find verified competitors - web search unavailable'"
}}"""

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

        # Pre-match competitors to simplify LLM's job
        matched_results = self._match_competitors(current_competitors, previous_competitors)

        prompt = f"""Analyze competitive changes for: {product_name}

**Competitors have been pre-matched. Your task is to:**
1. Validate the matches and assign status explanations
2. Assess significance of changes
3. Summarize key competitive shifts

**Pre-matched Results:**
{self._format_matched_competitors(matched_results)}

For each competitor, provide:
- status_explanation: Brief reason (e.g., "New market entrant", "Continuing competitor")
- significance: "low", "medium", or "high" based on competitive impact

Summary:
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

    def _match_competitors(self, current: List[Dict], previous: List[Dict]) -> List[Dict]:
        """
        Pre-match current competitors against previous ones using simple name/URL matching.
        This offloads the matching work from the LLM, making it faster.
        """
        import difflib

        matched = []
        previous_names = {comp.get('name', '').lower(): comp for comp in previous}

        for curr_comp in current:
            curr_name = curr_comp.get('name', '').lower()
            curr_url = curr_comp.get('url', '').lower()

            # Try exact name match first
            match = previous_names.get(curr_name)

            # Try fuzzy name match if no exact match
            if not match and previous:
                close_matches = difflib.get_close_matches(
                    curr_name,
                    previous_names.keys(),
                    n=1,
                    cutoff=0.8
                )
                if close_matches:
                    match = previous_names[close_matches[0]]

            # Try URL domain match as fallback
            if not match and curr_url and previous:
                curr_domain = curr_url.split('/')[2] if '/' in curr_url else curr_url
                for prev_comp in previous:
                    prev_url = prev_comp.get('url', '').lower()
                    prev_domain = prev_url.split('/')[2] if '/' in prev_url else prev_url
                    if curr_domain == prev_domain and curr_domain:
                        match = prev_comp
                        break

            matched.append({
                **curr_comp,
                'status': 'continuing' if match else 'new',
                'previous_match': match.get('id') if match else None
            })

        return matched

    def _format_matched_competitors(self, matched: List[Dict]) -> str:
        """Format pre-matched competitors for prompt"""
        if not matched:
            return "(None)"

        lines = []
        for comp in matched:
            status = comp.get('status', 'new')
            name = comp.get('name', 'Unknown')
            url = comp.get('url', 'N/A')
            lines.append(f"- [{status.upper()}] {name}: {url}")
        return '\n'.join(lines)

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
