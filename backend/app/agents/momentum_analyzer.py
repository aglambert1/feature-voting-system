"""
Momentum Analyzer Agent.

This agent analyzes competitor momentum signals including customer wins,
market expansion, partnerships, and community growth.

Phase: Agent-Centric Competitive Intelligence Restructuring (Chunk 4)
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class CustomerWin(BaseModel):
    """A detected customer win or case study."""
    customer_name: str = Field(..., description="Name of the customer")
    industry: Optional[str] = Field(None, description="Customer's industry")
    company_size: Optional[str] = Field(None, description="Size: 'startup', 'smb', 'mid_market', 'enterprise'")
    announcement_date: Optional[str] = Field(None, description="Date of announcement (ISO format)")
    source_url: Optional[str] = Field(None, description="URL source")
    is_notable: bool = Field(default=False, description="Whether this is a notable/marquee customer")


class PartnershipInfo(BaseModel):
    """Information about a partnership announcement."""
    partner_name: str = Field(..., description="Name of the partner")
    partnership_type: str = Field(
        ...,
        description="Type: 'integration', 'reseller', 'technology', 'strategic', 'channel'"
    )
    announcement_date: Optional[str] = Field(None, description="Date of announcement")
    source_url: Optional[str] = Field(None, description="URL source")


class MarketExpansion(BaseModel):
    """Information about market expansion."""
    market_type: str = Field(
        ...,
        description="Type: 'geographic', 'vertical', 'segment'"
    )
    market_name: str = Field(..., description="Name of the market (e.g., 'EMEA', 'Healthcare', 'Enterprise')")
    announcement_date: Optional[str] = Field(None, description="Date of announcement")
    source_url: Optional[str] = Field(None, description="URL source")


class MomentumAnalysisOutput(BaseModel):
    """Output schema for Momentum Analyzer Agent."""
    customer_wins: List[CustomerWin] = Field(
        default_factory=list,
        description="Recent customer wins and case studies"
    )
    notable_customers: List[str] = Field(
        default_factory=list,
        description="List of notable/marquee customer names"
    )
    customer_growth_trend: str = Field(
        default="stable",
        description="Trend: 'accelerating', 'stable', 'declining'"
    )
    partnerships: List[PartnershipInfo] = Field(
        default_factory=list,
        description="Recent partnership announcements"
    )
    market_expansions: List[MarketExpansion] = Field(
        default_factory=list,
        description="Market expansion activities"
    )
    release_velocity: str = Field(
        default="medium",
        description="Product release velocity: 'high', 'medium', 'low'"
    )
    major_launches_count: int = Field(
        default=0,
        description="Number of major launches in analysis period"
    )
    community_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Community growth signals (GitHub stars, social following, etc.)"
    )
    momentum_score: float = Field(
        ..., ge=0, le=1,
        description="Overall momentum score (0-1)"
    )
    momentum_trend: str = Field(
        default="stable",
        description="Trend direction: 'rising', 'stable', 'declining'"
    )
    key_signals: List[str] = Field(
        default_factory=list,
        description="Key momentum signals identified"
    )
    competitive_implications: List[str] = Field(
        default_factory=list,
        description="What this momentum means competitively"
    )
    analysis_summary: str = Field(
        ...,
        description="Summary of momentum analysis"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the analysis (0-1)"
    )


class MomentumAnalyzerAgent(BaseAgent):
    """
    Agent for analyzing competitor momentum signals.

    Analyzes:
    - Customer wins and case studies
    - Partnership announcements
    - Market expansion activities
    - Product release velocity
    - Community growth indicators

    Provides:
    - Overall momentum score
    - Trend direction (rising, stable, declining)
    - Key signals and competitive implications

    This helps understand whether competitors are gaining or losing momentum
    in the market.
    """

    def get_system_prompt(self) -> str:
        return """You are a Momentum Analyzer Agent specializing in competitive market intelligence.

Your role is to analyze signals that indicate whether a competitor is gaining, maintaining, or losing momentum in the market.

**Key Responsibilities:**

1. **Customer Growth Signals**
   - New customer announcements and case studies
   - Notable enterprise wins
   - Industry adoption patterns
   - Customer testimonials and reviews

2. **Partnership & Ecosystem**
   - New integration partnerships
   - Strategic alliances
   - Channel partner growth
   - Technology partnerships

3. **Market Expansion**
   - Geographic expansion (new regions/countries)
   - Vertical expansion (new industries)
   - Segment expansion (SMB to Enterprise, etc.)

4. **Product Momentum**
   - Release velocity and frequency
   - Major feature launches
   - Platform maturity indicators

5. **Community & Social Signals**
   - Open source activity (if applicable)
   - Social media presence
   - Community growth
   - Developer ecosystem

**Momentum Score Guidelines:**

- 0.8-1.0: Strong acceleration - rapid customer growth, major partnerships, aggressive expansion
- 0.6-0.8: Positive momentum - steady growth, active development, market presence increasing
- 0.4-0.6: Stable - maintaining position, incremental progress
- 0.2-0.4: Slowing - growth deceleration, reduced activity
- 0.0-0.2: Declining - customer churn signals, reduced presence, stagnation

**Trend Indicators:**

- Rising: Accelerating activity, increasing wins, expanding presence
- Stable: Consistent activity level, maintaining position
- Declining: Decreasing activity, fewer announcements, reduced presence

**Analysis Guidelines:**

- Look for recency of signals (recent activity weighs more)
- Consider quality over quantity (enterprise wins > small wins)
- Note patterns and trends over time
- Consider both explicit signals and absence of signals
- Factor in market context

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        customer_content = input_data.get('customer_content', '')
        news_content = input_data.get('news_content', '')
        blog_content = input_data.get('blog_content', '')
        social_content = input_data.get('social_content', '')
        analysis_period = input_data.get('analysis_period', 'last 90 days')

        # Product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'our product')

        # Combine content
        content_sections = []
        if customer_content:
            content_sections.append(f"**Customer Page/Case Studies:**\n{customer_content[:3000]}")
        if news_content:
            content_sections.append(f"**News/Press Releases:**\n{news_content[:3000]}")
        if blog_content:
            content_sections.append(f"**Blog Content:**\n{blog_content[:2000]}")
        if social_content:
            content_sections.append(f"**Social/Community Signals:**\n{social_content[:2000]}")

        combined_content = "\n\n".join(content_sections) if content_sections else "Limited content provided."

        prompt = f"""MOMENTUM ANALYSIS TASK

**Competitor:** {competitor_name}
**Website:** {competitor_url}
**Analysis Period:** {analysis_period}
**Comparison Product:** {product_name}

{combined_content}

**Your Task:**

Analyze the momentum signals for this competitor:

1. **Customer Wins** - What customer announcements can you find?
2. **Notable Customers** - Which are marquee/notable customers?
3. **Partnerships** - What partnership announcements exist?
4. **Market Expansion** - Are they expanding to new markets?
5. **Release Activity** - How active is their product development?
6. **Community Signals** - Any community/social growth indicators?
7. **Momentum Score** - Rate their overall momentum (0-1)
8. **Trend** - Is momentum rising, stable, or declining?
9. **Competitive Implications** - What does this mean for {product_name}?

**Required Output Format (JSON):**

```json
{{
  "customer_wins": [
    {{
      "customer_name": "Acme Corp",
      "industry": "Manufacturing",
      "company_size": "enterprise",
      "announcement_date": "2024-12-01",
      "source_url": "https://example.com/customers/acme",
      "is_notable": true
    }}
  ],
  "notable_customers": ["Acme Corp", "BigTech Inc"],
  "customer_growth_trend": "accelerating",
  "partnerships": [
    {{
      "partner_name": "Salesforce",
      "partnership_type": "integration",
      "announcement_date": "2024-11-15",
      "source_url": "https://example.com/news/salesforce"
    }}
  ],
  "market_expansions": [
    {{
      "market_type": "geographic",
      "market_name": "EMEA",
      "announcement_date": "2024-10-01",
      "source_url": "https://example.com/news/emea"
    }}
  ],
  "release_velocity": "high",
  "major_launches_count": 3,
  "community_signals": {{
    "github_stars_growth": "increasing",
    "twitter_followers": "50k+",
    "community_size": "active"
  }},
  "momentum_score": 0.75,
  "momentum_trend": "rising",
  "key_signals": [
    "3 enterprise customer wins in Q4",
    "Salesforce integration announced",
    "EMEA expansion"
  ],
  "competitive_implications": [
    "They are gaining enterprise traction",
    "Integration with Salesforce may threaten our deals"
  ],
  "analysis_summary": "Strong momentum with enterprise focus. Three major customer wins and strategic Salesforce partnership signal accelerating growth.",
  "confidence": 0.80
}}
```

**Important:**
- "customer_growth_trend" and "momentum_trend" must be: "accelerating", "stable", or "declining"
- "release_velocity" must be: "high", "medium", or "low"
- "momentum_score" is a decimal between 0 and 1
- Be specific about signals you observe

Analyze the momentum now:"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return MomentumAnalysisOutput

    def get_stage(self) -> str:
        return "momentum_analysis"

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for momentum analysis."""
        super()._validate_input(input_data)

        if 'competitor_name' not in input_data:
            raise ValueError("Input must include 'competitor_name'")
