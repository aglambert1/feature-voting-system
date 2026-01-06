"""
Financials Analyzer Agent.

This agent analyzes competitor financial information including funding,
revenue, and growth metrics when publicly available.

Phase: Agent-Centric Competitive Intelligence Restructuring (Chunk 4)
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class FundingRound(BaseModel):
    """Information about a funding round."""
    round_type: str = Field(
        ...,
        description="Type: 'seed', 'series_a', 'series_b', 'series_c', 'series_d', 'series_e', 'growth', 'ipo', 'debt', 'unknown'"
    )
    amount: Optional[float] = Field(None, description="Amount raised in USD")
    date: Optional[str] = Field(None, description="Date of funding (ISO format)")
    investors: List[str] = Field(default_factory=list, description="Lead investors")
    valuation: Optional[float] = Field(None, description="Post-money valuation if known")


class FinancialsAnalysisOutput(BaseModel):
    """Output schema for Financials Analyzer Agent."""
    company_type: str = Field(
        ...,
        description="Type: 'public', 'private', 'startup', 'acquired', 'unknown'"
    )
    total_funding: Optional[float] = Field(
        None,
        description="Total funding raised in USD (for private companies)"
    )
    funding_rounds: List[FundingRound] = Field(
        default_factory=list,
        description="List of funding rounds"
    )
    funding_stage: Optional[str] = Field(
        None,
        description="Current funding stage: 'seed', 'series_a', 'series_b', 'series_c', 'growth', 'public'"
    )
    last_funding_date: Optional[str] = Field(
        None,
        description="Date of most recent funding (ISO format)"
    )
    market_cap: Optional[float] = Field(
        None,
        description="Market capitalization in USD (for public companies)"
    )
    revenue_estimate: Optional[float] = Field(
        None,
        description="Estimated annual revenue in USD"
    )
    revenue_growth_yoy: Optional[float] = Field(
        None,
        description="Year-over-year revenue growth percentage"
    )
    employee_count: Optional[int] = Field(
        None,
        description="Estimated number of employees"
    )
    employee_growth_yoy: Optional[float] = Field(
        None,
        description="Year-over-year employee growth percentage"
    )
    financial_health: str = Field(
        default="unknown",
        description="Assessment: 'strong', 'moderate', 'weak', 'unknown'"
    )
    runway_estimate: Optional[str] = Field(
        None,
        description="Estimated runway for private companies (e.g., '18-24 months')"
    )
    notable_investors: List[str] = Field(
        default_factory=list,
        description="Notable investors (VCs, strategic investors)"
    )
    key_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Other key metrics (ARR, customers, etc.)"
    )
    competitive_implications: List[str] = Field(
        default_factory=list,
        description="What the financials mean competitively"
    )
    analysis_summary: str = Field(
        ...,
        description="Summary of financial analysis"
    )
    data_sources: List[str] = Field(
        default_factory=list,
        description="Sources used for this analysis"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the analysis (0-1)"
    )


class FinancialsAnalyzerAgent(BaseAgent):
    """
    Agent for analyzing competitor financial information.

    Analyzes:
    - Funding history and investors
    - Revenue and growth metrics
    - Employee count and growth
    - Market capitalization (public)
    - Financial health indicators

    Provides:
    - Financial health assessment
    - Competitive implications
    - Growth trajectory insights

    Note: Financial information may be limited for private companies.
    Confidence scores reflect data availability.
    """

    def get_system_prompt(self) -> str:
        return """You are a Financials Analyzer Agent specializing in competitive financial intelligence.

Your role is to analyze publicly available financial information about competitors to understand their resources, growth trajectory, and competitive position.

**Key Responsibilities:**

1. **Funding Analysis (Private Companies)**
   - Total funding raised
   - Funding rounds and investors
   - Current funding stage
   - Valuation estimates
   - Runway implications

2. **Public Company Metrics**
   - Market capitalization
   - Revenue and growth
   - Profitability indicators
   - Stock performance

3. **Growth Indicators**
   - Revenue growth
   - Employee growth
   - Customer growth (if known)
   - Market expansion

4. **Financial Health Assessment**
   - Strong: Well-funded, growing, profitable or clear path
   - Moderate: Adequate resources, steady growth
   - Weak: Limited runway, declining metrics
   - Unknown: Insufficient data

**Company Types:**
- public: Publicly traded company
- private: Private company with known funding
- startup: Early-stage startup
- acquired: Recently acquired
- unknown: Unable to determine

**Funding Stages:**
- seed: Pre-Series A funding
- series_a: Series A funding
- series_b: Series B funding
- series_c: Series C funding
- growth: Late-stage growth funding
- public: Public company

**Analysis Guidelines:**

- Use only publicly available information
- Be clear about what is factual vs. estimated
- Consider recency of financial data
- Note when information is limited or unavailable
- Account for industry context in assessments
- Financial data may be sensitive - stick to public sources

**Confidence Scoring:**

- 0.9-1.0: Public company with disclosed financials
- 0.7-0.9: Well-documented private company (Crunchbase, press)
- 0.5-0.7: Some financial information available
- 0.3-0.5: Limited information, significant estimation
- 0.0-0.3: Very limited or no financial information

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        funding_content = input_data.get('funding_content', '')
        news_content = input_data.get('news_content', '')
        careers_content = input_data.get('careers_content', '')
        crunchbase_content = input_data.get('crunchbase_content', '')

        # Product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'our product')

        # Combine content
        content_sections = []
        if crunchbase_content:
            content_sections.append(f"**Crunchbase/Financial Data:**\n{crunchbase_content[:3000]}")
        if funding_content:
            content_sections.append(f"**Funding Information:**\n{funding_content[:2000]}")
        if news_content:
            content_sections.append(f"**News/Press:**\n{news_content[:2000]}")
        if careers_content:
            content_sections.append(f"**Careers Page (for employee sizing):**\n{careers_content[:1500]}")

        combined_content = "\n\n".join(content_sections) if content_sections else "Limited financial content provided."

        prompt = f"""FINANCIALS ANALYSIS TASK

**Competitor:** {competitor_name}
**Website:** {competitor_url}
**Comparison Product:** {product_name}

{combined_content}

**Your Task:**

Analyze available financial information for this competitor:

1. **Company Type** - Public, private, startup, or acquired?
2. **Funding History** - What funding have they raised?
3. **Funding Stage** - What stage are they at?
4. **Revenue Estimates** - Any revenue information?
5. **Employee Count** - How many employees?
6. **Financial Health** - Strong, moderate, or weak?
7. **Notable Investors** - Who has invested?
8. **Competitive Implications** - What does this mean for {product_name}?

**Required Output Format (JSON):**

```json
{{
  "company_type": "private",
  "total_funding": 50000000,
  "funding_rounds": [
    {{
      "round_type": "series_b",
      "amount": 30000000,
      "date": "2024-06-15",
      "investors": ["Sequoia Capital", "a16z"],
      "valuation": 200000000
    }}
  ],
  "funding_stage": "series_b",
  "last_funding_date": "2024-06-15",
  "market_cap": null,
  "revenue_estimate": 15000000,
  "revenue_growth_yoy": 80,
  "employee_count": 150,
  "employee_growth_yoy": 50,
  "financial_health": "strong",
  "runway_estimate": "24+ months",
  "notable_investors": ["Sequoia Capital", "a16z", "First Round"],
  "key_metrics": {{
    "arr": 15000000,
    "customers": 500
  }},
  "competitive_implications": [
    "Well-funded competitor with strong runway",
    "Likely to invest heavily in product and go-to-market"
  ],
  "analysis_summary": "Series B funded startup with strong backing from top-tier VCs. Estimated ARR of $15M with 80% growth suggests healthy business. 24+ month runway provides stability for aggressive expansion.",
  "data_sources": ["Crunchbase", "TechCrunch", "Company blog"],
  "confidence": 0.75
}}
```

**Important:**
- "company_type" must be: "public", "private", "startup", "acquired", "unknown"
- "funding_stage" must be: "seed", "series_a", "series_b", "series_c", "growth", "public"
- "financial_health" must be: "strong", "moderate", "weak", "unknown"
- Use null for unknown numeric values
- "confidence" reflects data availability (0-1)

Analyze the financials now:"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return FinancialsAnalysisOutput

    def get_stage(self) -> str:
        return "financials_analysis"

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for financials analysis."""
        super()._validate_input(input_data)

        if 'competitor_name' not in input_data:
            raise ValueError("Input must include 'competitor_name'")
