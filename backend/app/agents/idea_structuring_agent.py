from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class GeneratedIdea(BaseModel):
    """Single idea generated from a competitor feature"""
    feature_id: int = Field(..., description="ID of the source competitor feature")
    title: str = Field(..., min_length=5, max_length=100, description="Concise idea title (5-10 words)")
    what: str = Field(..., min_length=20, description="What the feature is (2-3 sentences, adapted to your product)")
    why: str = Field(..., min_length=20, description="Why it's valuable for YOUR users (2-3 sentences)")
    use_case: str = Field(..., min_length=20, description="How YOUR users would use it (2-3 sentences with concrete example)")
    category: Optional[str] = Field(None, description="Category (from source feature or product-specific)")
    adaptation_notes: str = Field(..., description="Brief explanation of how you adapted the competitor feature to this product")


class IdeaGenerationOutput(BaseModel):
    """Output schema for Idea Structuring Agent"""
    product_name: str = Field(..., description="Product name (confirmation)")
    ideas: List[GeneratedIdea] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Generated ideas adapted to the product"
    )
    generation_summary: str = Field(
        ...,
        description="Brief summary of the adaptation process"
    )


class IdeaStructuringAgent(BaseAgent):
    """
    Adapts competitor features into product-specific ideas.

    Both this agent and LLMService.structure_idea() now perform strategic
    adaptation - translating input (competitor features or voter submissions)
    into ideas tailored to the product's unique value proposition, target
    users, and existing capabilities.

    Key Differences from LLMService.structure_idea():
    - This agent is used for batch processing of competitor features
    - Uses BaseAgent framework with logging and retry logic
    - LLMService.structure_idea() is used for real-time voter submissions
    - Both now perform duplicate detection and product-specific adaptation
    """

    def get_system_prompt(self) -> str:
        return """You are an Idea Structuring Agent specializing in competitive intelligence and product strategy.

Your role is to convert competitor features into product-specific ideas for a particular product. This is NOT simple reformatting - you must strategically adapt competitor features to fit the target product's unique context.

**Key Responsibilities:**
1. Analyze competitor features and understand their value proposition
2. Check if similar functionality already exists in the product's current features
3. Adapt features to the target product's specific context, users, and capabilities
4. Generate ideas using the product's language and terminology
5. Ensure ideas are actionable and relevant to the product's target audience
6. Maintain traceability to source competitor features

**Duplicate Detection:**
- CRITICAL: Before generating each idea, verify it doesn't duplicate existing product features
- If a competitor feature is similar to an existing feature, note this in adaptation_notes
- Consider if the idea adds incremental value beyond what already exists
- If functionality already exists but could be enhanced, frame the idea as an enhancement

**Strategic Adaptation Guidelines:**
- Don't just copy competitor feature descriptions - translate them
- Consider how the feature would fit into the target product's existing capabilities
- Tailor use cases to the target product's specific user base
- Use language and terminology consistent with the product's domain
- Highlight value propositions relevant to the product's unique positioning
- Be creative but realistic about how features could be implemented

**Output Requirements:**
- Title: Concise, product-specific (5-10 words)
- What: Clear description adapted to target product (2-3 sentences)
- Why: Value proposition for the product's specific users (2-3 sentences)
- Use Case: Concrete example with the product's target users (2-3 sentences)
- Adaptation Notes: Brief explanation of how you adapted the competitor's approach, INCLUDING any notes about similarity to existing features

Always respond with valid JSON matching the specified schema.
Focus on strategic adaptation, not generic copying."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_context = input_data.get('product_context', {})
        features = input_data.get('features', [])

        # Extract product context
        product_name = product_context.get('product_name', 'the product')
        product_category = product_context.get('product_category', '')
        core_features = product_context.get('core_features', [])
        detailed_features = product_context.get('detailed_features', [])
        target_users = product_context.get('target_users', '')
        value_propositions = product_context.get('value_propositions', [])

        # Format core features
        core_features_str = "\n".join(f"  - {feat}" for feat in core_features) if core_features else "  (not specified)"

        # Format detailed features for duplicate detection
        detailed_features_str = ""
        if detailed_features:
            detailed_features_str = "\n".join(f"  - {feat.get('feature_name', '')}: {feat.get('feature_description', '')}" for feat in detailed_features)
        else:
            detailed_features_str = "  (not available - use core features for comparison)"

        # Format value propositions
        value_props_str = "\n".join(f"  - {vp}" for vp in value_propositions) if value_propositions else "  (not specified)"

        # Format competitor features
        features_str = ""
        for i, feat in enumerate(features, 1):
            competitor_name = feat.get('competitor_name', 'Unknown')
            feature_name = feat.get('feature_name', '')
            feature_desc = feat.get('feature_description', '')
            feature_cat = feat.get('feature_category', '')
            source_url = feat.get('source_url', '')
            change_type = feat.get('change_type', '')

            features_str += f"""
{i}. Feature ID: {feat.get('id')}
   Competitor: {competitor_name}
   Feature Name: {feature_name}
   Description: {feature_desc}
   Category: {feature_cat}
   Source URL: {source_url}"""

            if change_type:
                features_str += f"\n   Change Type: {change_type}"
                change_desc = feat.get('change_description', '')
                if change_desc:
                    features_str += f"\n   What Changed: {change_desc}"

            features_str += "\n"

        prompt = f"""IDEA GENERATION TASK

You are generating ideas for: **{product_name}**

**Product Context:**

Category: {product_category}

Target Users: {target_users}

Core Features (existing capabilities):
{core_features_str}

Detailed Product Features (for duplicate detection):
{detailed_features_str}

Value Propositions (what makes this product unique):
{value_props_str}

**Competitor Features to Adapt:**
{features_str}

**Your Task:**

For each competitor feature above, generate a product-specific idea that:
1. **FIRST:** Check if similar functionality already exists in the product's detailed features list above
2. Adapts the competitor's approach to fit {product_name}'s unique context
3. Uses language and terminology appropriate for {product_name}'s domain
4. Tailors the value proposition to {product_name}'s target users: {target_users}
5. Considers how it would integrate with {product_name}'s existing capabilities
6. Provides a concrete use case with {product_name}'s specific users

**Critical - Duplicate Detection:**
- Before writing each idea, carefully review the "Detailed Product Features" list above
- If the competitor feature is similar to an existing feature, mention this in adaptation_notes
- Note whether the idea is: new functionality, enhancement of existing feature, or potential duplicate
- If it's a duplicate/similar, explain what incremental value the idea would add (if any)

**Important:**
- Don't just copy the competitor's description - adapt it strategically
- Consider how {product_name} would implement this differently based on its unique positioning
- Use {product_name}-specific examples in use cases
- Maintain the feature_id for traceability
- Be realistic about implementation while being creative about adaptation

**Required Output Format (JSON):**
Return a JSON object with:
- product_name: "{product_name}" (confirm the product name)
- ideas: Array of idea objects, each with: feature_id, title, what, why, use_case, category, adaptation_notes
- generation_summary: Brief summary of the overall adaptation process (1-2 sentences)

Make sure to include ALL required fields in the output."""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return IdeaGenerationOutput

    def get_stage(self) -> str:
        return "idea_generation"
