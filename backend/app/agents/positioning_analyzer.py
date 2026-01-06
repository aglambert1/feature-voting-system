"""
Positioning Analyzer Agent.

This agent analyzes competitor messaging and positioning to understand
their value propositions, target audience, and market positioning.

Phase: Agent-Centric Competitive Intelligence Restructuring (Chunk 4)
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class ValueProposition(BaseModel):
    """A key value proposition from competitor messaging."""
    claim: str = Field(..., description="The value claim or promise")
    supporting_evidence: Optional[str] = Field(None, description="Supporting evidence or proof points")
    target_pain_point: Optional[str] = Field(None, description="The pain point this addresses")


class PositioningAnalysisOutput(BaseModel):
    """Output schema for Positioning Analyzer Agent."""
    tagline: Optional[str] = Field(
        None,
        description="Main tagline or headline from their website"
    )
    value_propositions: List[ValueProposition] = Field(
        default_factory=list,
        description="Key value propositions from their messaging"
    )
    target_audience: str = Field(
        ...,
        description="Description of their target audience/ideal customer"
    )
    market_segment: str = Field(
        ...,
        description="Market segment: 'smb', 'mid_market', 'enterprise', 'consumer', 'all'"
    )
    key_differentiators: List[str] = Field(
        default_factory=list,
        description="Claimed differentiators from competitors"
    )
    positioning_statement: str = Field(
        ...,
        description="Summary positioning statement in the format: 'For [target], [product] is the [category] that [key benefit] unlike [alternatives]'"
    )
    messaging_themes: List[str] = Field(
        default_factory=list,
        description="Recurring themes in their messaging (e.g., 'simplicity', 'power', 'innovation')"
    )
    social_proof: List[str] = Field(
        default_factory=list,
        description="Types of social proof used (e.g., 'customer logos', 'case studies', 'reviews')"
    )
    competitive_claims: List[str] = Field(
        default_factory=list,
        description="Direct or indirect claims against competitors"
    )
    source_urls: List[str] = Field(
        default_factory=list,
        description="URLs analyzed for positioning"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the analysis (0-1)"
    )


class PositioningAnalyzerAgent(BaseAgent):
    """
    Agent for analyzing competitor positioning and messaging.

    Extracts:
    - Taglines and value propositions
    - Target audience and market segment
    - Key differentiators and competitive claims
    - Messaging themes and social proof
    - Synthesized positioning statement

    This information helps understand how competitors position themselves
    and identify opportunities for differentiation.
    """

    def get_system_prompt(self) -> str:
        return """You are a Positioning Analyzer Agent specializing in competitive messaging analysis.

Your role is to analyze competitor websites and marketing materials to understand their market positioning and messaging strategy.

**Key Responsibilities:**

1. **Identify Messaging Elements**
   - Main taglines and headlines
   - Value propositions and promises
   - Key differentiators they claim
   - Social proof and credibility indicators

2. **Determine Target Audience**
   - Who are they targeting? (SMB, enterprise, specific industries)
   - What pain points do they address?
   - What use cases do they emphasize?

3. **Analyze Competitive Positioning**
   - How do they position against alternatives?
   - What makes them claim to be unique?
   - Are there direct competitive claims?

4. **Synthesize Positioning Statement**
   - Create a clear positioning statement that captures their market position
   - Format: "For [target], [product] is the [category] that [key benefit] unlike [alternatives]"

**Market Segments:**
- smb: Small and medium businesses
- mid_market: Mid-sized companies
- enterprise: Large enterprises
- consumer: Individual consumers
- all: Targeting multiple segments

**Analysis Guidelines:**

- Focus on what they say, not what you infer
- Look for consistent messaging themes across pages
- Note the emotional appeals they use
- Identify proof points and credibility markers
- Consider both explicit and implicit positioning

**Confidence Scoring:**

- 0.9-1.0: Clear, consistent messaging across multiple sources
- 0.7-0.9: Good messaging clarity with some gaps
- 0.5-0.7: Mixed or unclear messaging
- 0.3-0.5: Limited messaging information
- 0.0-0.3: Very unclear or contradictory messaging

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        homepage_content = input_data.get('homepage_content', '')
        about_content = input_data.get('about_content', '')
        additional_content = input_data.get('additional_content', '')

        # Product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'our product')
        product_category = product_context.get('product_category', '')

        # Combine content
        content_sections = []
        if homepage_content:
            content_sections.append(f"**Homepage Content:**\n{homepage_content[:4000]}")
        if about_content:
            content_sections.append(f"**About Page Content:**\n{about_content[:2000]}")
        if additional_content:
            content_sections.append(f"**Additional Content:**\n{additional_content[:2000]}")

        combined_content = "\n\n".join(content_sections) if content_sections else "No content provided."

        prompt = f"""POSITIONING ANALYSIS TASK

**Competitor:** {competitor_name}
**Website:** {competitor_url}
**Product Category:** {product_category}

{combined_content}

**Your Task:**

Analyze the competitor's positioning and messaging to extract:

1. **Tagline** - What is their main headline or tagline?
2. **Value Propositions** - What key value claims do they make?
3. **Target Audience** - Who are they targeting?
4. **Market Segment** - SMB, mid-market, enterprise, consumer, or all?
5. **Differentiators** - What makes them claim to be unique?
6. **Positioning Statement** - Synthesize their position
7. **Messaging Themes** - What recurring themes appear?
8. **Social Proof** - What credibility elements do they use?
9. **Competitive Claims** - Any direct or indirect competitor references?

**Required Output Format (JSON):**

```json
{{
  "tagline": "Their main tagline or headline",
  "value_propositions": [
    {{
      "claim": "What they promise",
      "supporting_evidence": "How they back it up",
      "target_pain_point": "What problem this solves"
    }}
  ],
  "target_audience": "Description of their ideal customer",
  "market_segment": "enterprise",
  "key_differentiators": [
    "First differentiator",
    "Second differentiator"
  ],
  "positioning_statement": "For [target], {competitor_name} is the [category] that [key benefit] unlike [alternatives]",
  "messaging_themes": ["innovation", "simplicity", "power"],
  "social_proof": ["customer logos", "case studies", "G2 reviews"],
  "competitive_claims": ["Any competitive comparisons they make"],
  "source_urls": ["{competitor_url}"],
  "confidence": 0.85
}}
```

**Important:**
- "market_segment" must be one of: "smb", "mid_market", "enterprise", "consumer", "all"
- "confidence" is a decimal between 0 and 1
- Be specific in your analysis, avoid generic observations

Analyze the positioning now:"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return PositioningAnalysisOutput

    def get_stage(self) -> str:
        return "positioning_analysis"

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for positioning analysis."""
        super()._validate_input(input_data)

        if 'competitor_name' not in input_data:
            raise ValueError("Input must include 'competitor_name'")

        # Should have some content to analyze
        if not any([
            input_data.get('homepage_content'),
            input_data.get('about_content'),
            input_data.get('additional_content')
        ]):
            raise ValueError("Input must include at least one of 'homepage_content', 'about_content', or 'additional_content'")
