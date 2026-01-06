"""
Intensity Idea Generator Agent.

This agent generates product ideas from high-intensity feature clusters.
When multiple competitors have similar features, it indicates a market
expectation that should be considered for the product roadmap.

Phase: Agent-Centric Competitive Intelligence Restructuring (Chunk 3)
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class CompetitiveFeatureInfo(BaseModel):
    """Information about a competitor's feature in the cluster."""
    competitor_name: str = Field(..., description="Name of the competitor")
    feature_name: str = Field(..., description="Name of the feature")
    feature_description: str = Field(default="", description="Description of the feature")


class GeneratedIdeaOutput(BaseModel):
    """Output schema for Intensity Idea Generator Agent."""
    title: str = Field(
        ...,
        max_length=255,
        description="Clear, concise title for the idea (max 255 chars)"
    )
    what_description: str = Field(
        ...,
        description="What is the feature? Detailed description of what should be built"
    )
    why_description: str = Field(
        ...,
        description="Why is this valuable? Business justification including competitive context"
    )
    use_case_description: str = Field(
        ...,
        description="How would it be used? Concrete user scenarios and workflows"
    )
    category: str = Field(
        ...,
        description="Suggested category for the idea"
    )
    competitive_urgency: str = Field(
        default="medium",
        description="Urgency level: 'low', 'medium', 'high', 'critical'"
    )
    urgency_reasoning: str = Field(
        ...,
        description="Explanation of why this urgency level was assigned"
    )
    differentiation_opportunities: List[str] = Field(
        default_factory=list,
        description="Ways to differentiate from competitor implementations"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the idea quality (0-1)"
    )


class IntensityIdeaGeneratorAgent(BaseAgent):
    """
    Agent for generating product ideas from high-intensity feature clusters.

    This agent is invoked when feature clustering identifies that multiple
    competitors (meeting the intensity threshold) have similar features.
    The agent synthesizes the cluster into an actionable product idea.

    Key responsibilities:
    1. Synthesize multiple competitor features into a unified concept
    2. Create a clear, actionable idea with what/why/use_case structure
    3. Assess competitive urgency based on cluster intensity
    4. Identify differentiation opportunities
    5. Provide a confidence score for idea quality

    The generated idea is then sent to the Idea Triage Agent for:
    - Deduplication against existing ideas
    - Matching against existing product features
    - PM recommendation generation
    """

    # Urgency thresholds based on competitor percentage
    URGENCY_THRESHOLDS = {
        "critical": 0.75,  # 75%+ of competitors have this
        "high": 0.50,      # 50-74% of competitors have this
        "medium": 0.30,    # 30-49% of competitors have this
        "low": 0.0         # Less than 30% of competitors have this
    }

    def get_system_prompt(self) -> str:
        return """You are an Intensity Idea Generator Agent for a competitive intelligence system.

Your role is to synthesize feature clusters from multiple competitors into actionable product ideas. When multiple competitors have similar features, it indicates market expectations that the product team should consider.

**Key Responsibilities:**

1. **Feature Synthesis**
   - Analyze the features from multiple competitors in the cluster
   - Identify the core concept that unites them
   - Understand the underlying user need being addressed

2. **Idea Generation**
   - Create a clear, specific title (not generic)
   - Write a detailed "What" description explaining the feature
   - Provide compelling "Why" justification including competitive context
   - Include concrete "Use Case" scenarios with user workflows

3. **Urgency Assessment**
   - CRITICAL: 75%+ of competitors have this feature (table stakes)
   - HIGH: 50-74% of competitors have this feature (market expectation)
   - MEDIUM: 30-49% of competitors have this feature (competitive advantage)
   - LOW: Less than 30% of competitors (nice to have)

4. **Differentiation Opportunities**
   - Identify ways to implement the feature better than competitors
   - Suggest unique angles or enhancements
   - Consider integration opportunities with existing product features

**Quality Standards:**

- Ideas must be specific and actionable, not vague concepts
- What/Why/Use Case must each provide distinct value
- Avoid generic language like "improve" or "enhance" without specifics
- Include concrete examples in use cases
- Reference competitive context in the "Why" section

**Output Requirements:**

Provide a structured JSON response with:
- A clear, specific title (max 255 characters)
- Detailed what/why/use_case descriptions
- Appropriate category
- Competitive urgency with reasoning
- Differentiation opportunities
- Confidence score (0-1)

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        # Extract cluster information
        cluster_name = input_data.get('cluster_name', 'Unknown Cluster')
        cluster_description = input_data.get('cluster_description', '')
        competitor_count = input_data.get('competitor_count', 0)
        total_competitors = input_data.get('total_competitors', 0)

        # Extract competitor features
        features = input_data.get('features', [])

        # Extract product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'the product')
        product_category = product_context.get('product_category', '')
        product_description = product_context.get('product_description', '')

        # Calculate competitor percentage for urgency
        competitor_percentage = (competitor_count / total_competitors * 100) if total_competitors > 0 else 0

        # Determine suggested urgency
        if competitor_percentage >= 75:
            suggested_urgency = "CRITICAL"
        elif competitor_percentage >= 50:
            suggested_urgency = "HIGH"
        elif competitor_percentage >= 30:
            suggested_urgency = "MEDIUM"
        else:
            suggested_urgency = "LOW"

        # Format competitor features
        if features:
            features_str = "\n".join([
                f"  - **{f.get('competitor_name', 'Unknown')}**: {f.get('feature_name', 'Unnamed')}\n"
                f"    Description: {f.get('feature_description', 'No description')}"
                for f in features
            ])
        else:
            features_str = "  No feature details available."

        prompt = f"""INTENSITY-BASED IDEA GENERATION TASK

**Product Context:**
- Product Name: {product_name}
- Category: {product_category}
- Description: {product_description[:500] + '...' if len(product_description) > 500 else product_description}

**Feature Cluster Information:**
- Cluster Name: {cluster_name}
- Cluster Description: {cluster_description}
- Competitor Coverage: {competitor_count} of {total_competitors} competitors ({competitor_percentage:.0f}%)
- Suggested Urgency: {suggested_urgency}

**Competitor Features in This Cluster:**
{features_str}

**Your Task:**

Generate a product idea based on this feature cluster. The idea should:

1. **Synthesize** the competitor features into a unified, actionable concept
2. **Be specific** - avoid generic descriptions, include concrete details
3. **Consider the product context** - how would this fit into {product_name}?
4. **Address the competitive pressure** - {competitor_count} competitors have this!

**Guidelines:**

- Title: Clear, specific, max 255 characters (e.g., "AI-Powered Search with Natural Language Queries" not just "Better Search")
- What: Detailed feature description including key capabilities and scope
- Why: Business justification referencing competitive context ({competitor_count}/{total_competitors} competitors = {competitor_percentage:.0f}% market coverage)
- Use Case: Concrete user scenario with step-by-step workflow
- Category: Suggest an appropriate category (e.g., "Search", "Collaboration", "Analytics")
- Urgency: Use {suggested_urgency} as the baseline, adjust if you have strong reasoning
- Differentiation: 2-3 ways to do this better than competitors

**Required Output Format (JSON):**

```json
{{
  "title": "Specific feature title under 255 chars",
  "what_description": "Detailed description of what the feature does and includes",
  "why_description": "Business justification referencing competitive pressure and user value",
  "use_case_description": "Concrete scenario: User opens X, clicks Y, sees Z. Include workflow steps.",
  "category": "Feature Category",
  "competitive_urgency": "medium",
  "urgency_reasoning": "Explanation of urgency level based on competitor coverage",
  "differentiation_opportunities": [
    "Specific way to do it better than competitors",
    "Another differentiation opportunity",
    "Integration with existing product feature"
  ],
  "confidence": 0.85
}}
```

**Important Notes:**
- "competitive_urgency" must be one of: "low", "medium", "high", "critical"
- "confidence" is a decimal between 0 and 1
- "differentiation_opportunities" must be a list of strings
- All descriptions should be detailed and specific, not generic

Generate the idea now:"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return GeneratedIdeaOutput

    def get_stage(self) -> str:
        return "intensity_idea_generation"

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for idea generation."""
        super()._validate_input(input_data)

        # Must have cluster information
        if 'cluster_name' not in input_data:
            raise ValueError("Input must include 'cluster_name'")

        # Must have feature information
        if 'features' not in input_data or not input_data['features']:
            raise ValueError("Input must include non-empty 'features' list")

        # Must have competitor counts
        if 'competitor_count' not in input_data:
            raise ValueError("Input must include 'competitor_count'")

        if 'total_competitors' not in input_data:
            raise ValueError("Input must include 'total_competitors'")

    def calculate_urgency(
        self,
        competitor_count: int,
        total_competitors: int
    ) -> str:
        """
        Calculate competitive urgency based on competitor coverage.

        Args:
            competitor_count: Number of competitors with this feature
            total_competitors: Total number of analyzed competitors

        Returns:
            Urgency level string: "critical", "high", "medium", or "low"
        """
        if total_competitors == 0:
            return "low"

        percentage = competitor_count / total_competitors

        if percentage >= self.URGENCY_THRESHOLDS["critical"]:
            return "critical"
        elif percentage >= self.URGENCY_THRESHOLDS["high"]:
            return "high"
        elif percentage >= self.URGENCY_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"
