"""
Product Analyzer Agent for competitive intelligence.

This agent analyzes product descriptions and extracts structured information
for competitive analysis. When web search is enabled (default), it supplements
user-provided data with web research to build a comprehensive product profile.
"""

from typing import Dict, Any, Optional, Type, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.services.search_service import get_search_service


class DetailedProductFeature(BaseModel):
    """Detailed product feature schema."""
    name: str = Field(..., max_length=255, description="Feature name (2-5 words)")
    description: str = Field(..., description="Feature description (1-2 sentences)")
    category: str = Field(..., description="Feature category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source_reference: str = Field(None, description="Where this feature was found")


class ProductAnalysisOutput(BaseModel):
    """Output schema for Product Analyzer Agent."""
    product_name: str = Field(..., description="Extracted or confirmed product name")
    product_category: str = Field(..., description="Product category/industry")
    core_features: list[str] = Field(
        ...,
        description="5-7 strategic core features that define the product",
        min_length=3,
        max_length=10
    )
    detailed_features: list[DetailedProductFeature] = Field(
        ...,
        description="All detailed tactical features extracted from all sources",
        min_length=5,
        max_length=200
    )
    target_users: str = Field(..., description="Target users/customers description")
    value_propositions: list[str] = Field(
        ...,
        description="Unique value propositions",
        min_length=1,
        max_length=5
    )
    competitor_search_keywords: list[str] = Field(
        ...,
        description="Keywords for finding competitors",
        min_length=3,
        max_length=10
    )
    pricing_tiers: Optional[list[dict]] = Field(
        None,
        description="Pricing tiers if discoverable (name, price, key features)"
    )
    integrations: Optional[list[str]] = Field(
        None,
        description="Known integrations/ecosystem connections"
    )
    data_sources: list[str] = Field(
        default_factory=list,
        description="Sources used for this analysis (e.g. 'provided_description', 'web:url')"
    )


class ProductAnalyzerAgent(BaseAgent):
    """
    Analyzes product descriptions and structures them for competitive analysis.

    When web_research_enabled=True (default), the agent uses web search to
    supplement user-provided data — searching for features, pricing, integrations,
    and reviews to build a comprehensive product profile.

    When web_research_enabled=False, the agent only analyzes the provided text.
    """

    def __init__(self, *args, web_research_enabled: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_service = get_search_service()
        self.web_research_enabled = web_research_enabled

    def get_tools(self) -> List[Dict[str, Any]]:
        """Provide web search tool if enabled and available."""
        if self.web_research_enabled and self.search_service.is_available():
            return [self.search_service.get_tool_definition()]
        return []

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute web search tool."""
        if tool_name == "web_search":
            query = tool_input.get("query", "")
            max_results = tool_input.get("max_results", 10)

            results = self.search_service.search(query, max_results)

            if not results:
                return "No search results found. Continue with available information."

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
        has_search = self.web_research_enabled and self.search_service.is_available()

        if has_search:
            return """You are a Product Intelligence agent specializing in B2B SaaS analysis.

Your task is to build a comprehensive product profile using ALL available information.

## Research Strategy
1. ANALYZE the provided product description to understand the product's core purpose and identity.
2. SEARCH for additional information to fill gaps and verify claims:
   - Search "[product name] features" for official feature lists
   - Search "[product name] pricing plans" for pricing tier information
   - Search "[product name] integrations" for ecosystem/connectivity data
   - Search "[product name] reviews G2" or "Capterra" for user perspectives on strengths/weaknesses
   - Search "[product name] API documentation" for technical capabilities
   - Search "[product name] vs" for competitive positioning context
3. SYNTHESIZE all sources into a comprehensive, evidence-backed profile.

## Source Attribution
For each detailed feature, set source_reference to indicate provenance:
- "provided" — directly from the user's input description
- "web:[domain]" — discovered via web search (cite the source domain)
- "knowledge" — from your training data (use lower confidence: 0.5-0.7)

## Feature Extraction Guidelines
- Extract 15-30 detailed features (aim for comprehensive coverage)
- Use standard categories: Core Functionality, UX/UI, Integrations, Security/Compliance, AI/Automation, Reporting/Analytics, Administration, Mobile, Collaboration
- Include pricing tiers if you find them (name, price range, key feature gates)
- Include integrations list if discoverable
- Set data_sources to list all sources consulted

## Quality Standards
- Be specific: "AI-powered receipt scanning with OCR" not just "AI features"
- Move past marketing language to identify actual capabilities
- Cross-reference web results with provided description for accuracy
- If web search returns no useful results, rely on provided description + training knowledge
- Never fabricate features — only include what you can verify from a source

Always respond with valid JSON matching the specified schema.
Do not include any markdown formatting or code blocks — just the raw JSON."""
        else:
            return """You are a Product Analyzer agent specializing in competitive intelligence.

Your role is to analyze product descriptions and extract structured information that will be used to:
1. Find competing products
2. Compare features across competitors
3. Generate strategic insights

You must be thorough but concise. Focus on aspects relevant to competitive analysis.
Extract as many verifiable features as possible from the provided description.

Set source_reference to "provided" for features from the description, or "knowledge" for features from your training data (use lower confidence for these).

Always respond with valid JSON matching the specified schema.
Do not include any markdown formatting or code blocks — just the raw JSON."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get('product_name', '')
        product_description = input_data.get('product_description', '')
        source_type = input_data.get('source_type', 'text')
        has_search = self.web_research_enabled and self.search_service.is_available()

        search_instructions = ""
        if has_search:
            search_instructions = f"""
## Web Research Instructions
Use the web_search tool to supplement the provided description. Suggested searches:
1. "{product_name} features" — official feature list
2. "{product_name} pricing" — pricing tiers and plans
3. "{product_name} integrations" — ecosystem connections
4. "{product_name} reviews" — user perspective on capabilities
Make 3-5 targeted searches. Skip searches that seem unlikely to yield results for this product type.
"""

        prompt = f"""Analyze the following product and build a comprehensive profile.

Product Name: {product_name if product_name else "(extract from description)"}
Source Type: {source_type}

Product Description:
{product_description}
{search_instructions}
## Required Output (JSON)

Return a JSON object with these fields:

1. **product_name**: The product name
2. **product_category**: Industry/category (e.g., "Expense Management Software")
3. **core_features**: 5-7 strategic high-level features that define this product
4. **detailed_features**: 15-30 specific features, each with:
   - name: 2-5 word feature name
   - description: 1-2 sentence description of what it actually does
   - category: One of: Core Functionality, UX/UI, Integrations, Security/Compliance, AI/Automation, Reporting/Analytics, Administration, Mobile, Collaboration
   - confidence: 0.0-1.0 (higher for features directly from provided description or web sources)
   - source_reference: "provided", "web:[domain]", or "knowledge"
5. **target_users**: Who uses this product (roles, company sizes, industries)
6. **value_propositions**: 2-4 unique competitive advantages
7. **competitor_search_keywords**: 5-10 keywords for finding competing products
8. **pricing_tiers**: If discoverable, list of {{"name": "...", "price": "...", "features": [...]}} — null if unknown
9. **integrations**: List of known integrations — null if unknown
10. **data_sources**: List of sources used (e.g., ["provided_description", "web:g2.com", "web:concur.com"])

IMPORTANT:
- Extract ALL verifiable features, not just a handful
- Be specific about what each feature does, not just its name
- Prioritize features from provided description and web sources over training knowledge
- Return ONLY the JSON object, no additional text"""

        return prompt

    def build_concise_user_prompt(self, input_data: Dict[str, Any]) -> Optional[str]:
        """Build a concise prompt for truncation recovery (no web search)."""
        product_name = input_data.get('product_name', '')
        product_description = input_data.get('product_description', '')
        source_type = input_data.get('source_type', 'text')

        return f"""Analyze the following product and extract structured data.

CRITICAL CONSTRAINT: A previous analysis was cut off because the response was too long.
You MUST follow these HARD LIMITS exactly:

1. detailed_features: EXACTLY 20 items. Not 21, not 30. Exactly 20.
2. Each description: MAXIMUM 10 words.
3. Each source_reference: MAXIMUM 4 words.
4. No markdown, no explanatory text — raw JSON only.

Pick the 20 most competitively important features. Omit the rest entirely.

Product Name: {product_name if product_name else "(extract from description)"}
Source Type: {source_type}
Product Description:
{product_description}

Return a JSON object with these fields:
- product_name (string)
- product_category (string)
- core_features (list of 5-7 strings)
- detailed_features (list of EXACTLY 20 objects: name, description, category, confidence, source_reference)
- target_users (string, max 30 words)
- value_propositions (list of 2-4 strings)
- competitor_search_keywords (list of 5-10 strings)
- pricing_tiers (null)
- integrations (null)
- data_sources (list of sources used)

Return ONLY the JSON object."""

    def get_output_schema(self) -> Type[BaseModel]:
        return ProductAnalysisOutput

    def get_stage(self) -> str:
        return "product_analysis"
