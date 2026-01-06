"""
Pricing Analyzer Agent.

This agent analyzes competitor pricing pages to extract pricing models,
tiers, and trial information.

Phase: Agent-Centric Competitive Intelligence Restructuring (Chunk 4)
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class PricingTier(BaseModel):
    """Information about a single pricing tier."""
    name: str = Field(..., description="Name of the tier (e.g., 'Free', 'Pro', 'Enterprise')")
    price: Optional[float] = Field(None, description="Price amount (null for custom/contact)")
    billing_period: str = Field(default="monthly", description="Billing period: 'monthly', 'yearly', 'one_time', 'custom'")
    currency: str = Field(default="USD", description="Currency code")
    features: List[str] = Field(default_factory=list, description="Key features included in this tier")
    limits: Dict[str, Any] = Field(default_factory=dict, description="Usage limits (e.g., {'users': 5, 'storage': '10GB'})")
    is_popular: bool = Field(default=False, description="Whether this tier is marked as popular/recommended")


class PricingAnalysisOutput(BaseModel):
    """Output schema for Pricing Analyzer Agent."""
    pricing_model: str = Field(
        ...,
        description="Pricing model: 'freemium', 'free_trial', 'subscription', 'usage_based', 'one_time', 'hybrid', 'contact_sales'"
    )
    has_free_tier: bool = Field(
        default=False,
        description="Whether a free tier is available"
    )
    has_trial: bool = Field(
        default=False,
        description="Whether a free trial is offered"
    )
    trial_days: Optional[int] = Field(
        None,
        description="Number of days for free trial (if applicable)"
    )
    pricing_tiers: List[PricingTier] = Field(
        default_factory=list,
        description="List of pricing tiers with details"
    )
    has_enterprise: bool = Field(
        default=False,
        description="Whether enterprise/custom pricing is available"
    )
    annual_discount: Optional[float] = Field(
        None,
        description="Discount percentage for annual billing (e.g., 20 for 20%)"
    )
    starting_price: Optional[float] = Field(
        None,
        description="Lowest non-free price point"
    )
    source_url: Optional[str] = Field(
        None,
        description="URL of the pricing page analyzed"
    )
    key_insights: List[str] = Field(
        default_factory=list,
        description="Notable insights about the pricing strategy"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the analysis (0-1)"
    )


class PricingAnalyzerAgent(BaseAgent):
    """
    Agent for analyzing competitor pricing pages.

    Extracts:
    - Pricing model (freemium, subscription, usage-based, etc.)
    - Available tiers with prices and features
    - Free tier and trial availability
    - Enterprise/custom pricing options
    - Annual discount information

    This information helps understand competitive positioning and pricing strategy.
    """

    def get_system_prompt(self) -> str:
        return """You are a Pricing Analyzer Agent specializing in competitive intelligence.

Your role is to analyze competitor pricing information and extract structured data about their pricing strategy.

**Key Responsibilities:**

1. **Identify Pricing Model**
   - Freemium: Free tier with paid upgrades
   - Free Trial: Trial period before requiring payment
   - Subscription: Recurring payment model
   - Usage-based: Pay per use/consumption
   - One-time: Single purchase
   - Hybrid: Combination of models
   - Contact Sales: Enterprise-only pricing

2. **Extract Tier Information**
   - Tier names and pricing
   - Billing periods (monthly, yearly)
   - Key features per tier
   - Usage limits and restrictions
   - Popular/recommended tier marking

3. **Identify Special Offers**
   - Free tier availability
   - Trial period details
   - Annual billing discounts
   - Enterprise options

4. **Provide Strategic Insights**
   - Notable pricing strategies
   - Competitive positioning signals
   - Value proposition alignment

**Analysis Guidelines:**

- Be thorough but focus on actionable pricing intelligence
- Note when information is unclear or requires assumptions
- Convert all prices to monthly equivalents for comparison
- Identify the target customer segment for each tier
- Flag unusual or aggressive pricing strategies

**Confidence Scoring:**

- 0.9-1.0: Clear, complete pricing information
- 0.7-0.9: Most information available, some assumptions needed
- 0.5-0.7: Partial information, moderate assumptions
- 0.3-0.5: Limited information, significant uncertainty
- 0.0-0.3: Very limited or unclear pricing data

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        pricing_url = input_data.get('pricing_url', '')
        pricing_content = input_data.get('pricing_content', '')

        # Product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'our product')

        prompt = f"""PRICING ANALYSIS TASK

**Competitor:** {competitor_name}
**Website:** {competitor_url}
**Pricing Page:** {pricing_url}

**Pricing Page Content:**
{pricing_content[:8000] if pricing_content else "No pricing content provided."}

**Your Task:**

Analyze the pricing information and extract:

1. **Pricing Model** - What type of pricing model do they use?
2. **Tiers** - What pricing tiers are available? Include:
   - Name, price, billing period
   - Key features included
   - Usage limits (users, storage, etc.)
3. **Free Options** - Is there a free tier or free trial?
4. **Enterprise** - Do they offer enterprise/custom pricing?
5. **Discounts** - Any annual billing discounts?
6. **Key Insights** - Notable strategic observations

**Required Output Format (JSON):**

```json
{{
  "pricing_model": "subscription",
  "has_free_tier": true,
  "has_trial": true,
  "trial_days": 14,
  "pricing_tiers": [
    {{
      "name": "Free",
      "price": 0,
      "billing_period": "monthly",
      "currency": "USD",
      "features": ["Basic features", "Up to 3 users"],
      "limits": {{"users": 3, "storage": "1GB"}},
      "is_popular": false
    }},
    {{
      "name": "Pro",
      "price": 29,
      "billing_period": "monthly",
      "currency": "USD",
      "features": ["All Free features", "Unlimited users", "Priority support"],
      "limits": {{"storage": "100GB"}},
      "is_popular": true
    }}
  ],
  "has_enterprise": true,
  "annual_discount": 20,
  "starting_price": 29,
  "source_url": "{pricing_url or competitor_url}",
  "key_insights": [
    "Aggressive free tier to capture market share",
    "Enterprise pricing targets large organizations"
  ],
  "confidence": 0.85
}}
```

**Important:**
- "pricing_model" must be one of: "freemium", "free_trial", "subscription", "usage_based", "one_time", "hybrid", "contact_sales"
- "billing_period" must be one of: "monthly", "yearly", "one_time", "custom"
- All prices should be in the original currency found
- "confidence" is a decimal between 0 and 1

Analyze the pricing now:"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return PricingAnalysisOutput

    def get_stage(self) -> str:
        return "pricing_analysis"

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for pricing analysis."""
        super()._validate_input(input_data)

        if 'competitor_name' not in input_data:
            raise ValueError("Input must include 'competitor_name'")

        # Should have some content to analyze
        if not input_data.get('pricing_content') and not input_data.get('pricing_url'):
            raise ValueError("Input must include 'pricing_content' or 'pricing_url'")
