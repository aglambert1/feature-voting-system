"""
Idea Triage Agent for auto-categorization and duplicate detection.

This agent processes new idea submissions to:
1. Generate embedding for similarity search
2. Find similar/duplicate ideas
3. Check competitive context (which competitors have this feature)
4. Generate auto-response for customer acknowledgment
5. Generate PM recommendation (approve/merge/review/reject)

Phase 3: Idea Normalization + Triage
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent


class SimilarIdeaInfo(BaseModel):
    """Information about a similar idea found."""
    idea_id: int = Field(..., description="ID of the similar idea")
    title: str = Field(..., description="Title of the similar idea")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    is_duplicate: bool = Field(..., description="Whether this is considered a duplicate")


class CompetitiveContext(BaseModel):
    """Competitive context for an idea."""
    competitors_with_feature: List[str] = Field(
        default_factory=list,
        description="Names of competitors that have similar features"
    )
    competitive_urgency: str = Field(
        default="low",
        description="Urgency level: 'low', 'medium', 'high', 'critical'"
    )
    competitor_count: int = Field(
        default=0,
        description="Number of competitors with this feature"
    )
    total_competitors_analyzed: int = Field(
        default=0,
        description="Total number of competitors analyzed"
    )
    urgency_reasoning: str = Field(
        default="",
        description="Structured explanation of the urgency assessment"
    )
    market_timing_notes: Optional[str] = Field(
        None,
        description="Additional notes about market timing and competitive pressure"
    )


class TriageRecommendation(BaseModel):
    """Recommendation from the triage agent."""
    action: str = Field(
        ...,
        description="Recommended action: 'approve', 'merge', 'review', 'reject'"
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in recommendation (0-1)"
    )
    reasoning: str = Field(
        ...,
        description="Explanation for the recommendation"
    )
    merge_target_id: Optional[int] = Field(
        None,
        description="If action is 'merge', the ID of the idea to merge with"
    )


class IdeaTriageOutput(BaseModel):
    """Output schema for Idea Triage Agent."""
    idea_summary: str = Field(
        ...,
        description="Brief summary of the idea (1-2 sentences)"
    )
    category: str = Field(
        ...,
        description="Suggested category for the idea"
    )
    category_confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in category assignment"
    )
    similar_ideas_analysis: str = Field(
        ...,
        description="Analysis of similar ideas found (or 'No similar ideas found')"
    )
    competitive_context: CompetitiveContext = Field(
        ...,
        description="Competitive context for the idea"
    )
    auto_response_text: str = Field(
        ...,
        description="Auto-response message for customer acknowledgment"
    )
    recommendation: TriageRecommendation = Field(
        ...,
        description="Triage recommendation"
    )


class IdeaTriageAgent(BaseAgent):
    """
    Agent for triaging new idea submissions.

    Processes ideas to:
    - Categorize automatically
    - Detect duplicates
    - Assess competitive context
    - Generate customer auto-response
    - Recommend action (approve/merge/review/reject)

    Thresholds (from spec):
    - >0.9 confidence = auto-approve
    - <0.5 confidence = reject
    - else = queue for PM review
    """

    AUTO_APPROVE_THRESHOLD = 0.9
    REJECT_THRESHOLD = 0.5

    def get_system_prompt(self) -> str:
        return """You are an Idea Triage Agent for a product feedback system.

Your role is to analyze new feature ideas and provide intelligent triage decisions to help product managers efficiently process incoming suggestions.

**Key Responsibilities:**

1. **Categorization**
   - Assign ideas to appropriate categories based on content
   - Use product-specific categories when available
   - Be consistent with existing categorization patterns

2. **Duplicate Analysis**
   - Review similar ideas provided in the input
   - Determine if the new idea is a true duplicate, related, or unique
   - If duplicate, identify which idea it should merge with

3. **Competitive Context**
   - Identify if competitors have similar features
   - Assess competitive urgency (how important is it to have this?)
   - Consider market timing implications

4. **Auto-Response Generation**
   - Create a friendly acknowledgment message for the submitter
   - Reference specific elements from their submission
   - Set appropriate expectations about next steps
   - Maintain a professional but warm tone

5. **Recommendation**
   - APPROVE: High-quality, unique idea ready for voting (confidence > 0.9)
   - MERGE: Clear duplicate of existing idea (provide merge target)
   - REVIEW: Needs PM review (ambiguous, sensitive, or moderate confidence)
   - REJECT: Low quality, off-topic, or clearly inappropriate (confidence < 0.5)

**Decision Guidelines:**

- Default to REVIEW when uncertain
- Consider the product's current priorities and roadmap
- Weight competitive pressure appropriately
- Be generous with approval for clear, actionable ideas
- Reserve rejection for clearly problematic submissions

**Output Requirements:**

Provide a structured analysis including:
- Brief idea summary
- Category assignment with confidence
- Analysis of similar ideas
- Competitive context assessment
- Auto-response for customer
- Clear recommendation with reasoning

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        # Extract idea details
        idea = input_data.get('idea', {})
        title = idea.get('title', '')
        what = idea.get('what_description', '')
        why = idea.get('why_description', '')
        use_case = idea.get('use_case_description', '')
        source_type = idea.get('source_type', 'customer_submission')

        # Extract product context
        product_context = input_data.get('product_context', {})
        product_name = product_context.get('product_name', 'the product')
        product_category = product_context.get('product_category', '')
        existing_categories = product_context.get('existing_categories', [])

        # Extract similar ideas from similarity detection
        similar_ideas = input_data.get('similar_ideas', [])

        # Extract competitive context (new structured format from SimilarityDetectorService)
        competitive_context = input_data.get('competitive_context', {})
        competitive_matches = competitive_context.get('matches', [])
        competitive_urgency = competitive_context.get('urgency', {})

        # Format similar ideas
        if similar_ideas:
            similar_ideas_str = "\n".join([
                f"  - ID {s['idea_id']}: \"{s['title']}\" (similarity: {s['similarity_score']:.2f}, "
                f"{'DUPLICATE' if s.get('is_duplicate') else 'similar'})"
                for s in similar_ideas
            ])
        else:
            similar_ideas_str = "  No similar ideas found."

        # Format competitive matches with structured urgency
        if competitive_matches:
            competitors_str = "\n".join([
                f"  - {c['competitor_name']}: {c['feature_name']} (similarity: {c.get('similarity_score', 'N/A')})"
                for c in competitive_matches
            ])
        else:
            competitors_str = "  No matching competitor features found."

        # Format structured urgency assessment
        if competitive_urgency:
            urgency_level = competitive_urgency.get('urgency', 'low').upper()
            urgency_reasoning = competitive_urgency.get('reasoning', '')
            competitor_count = competitive_urgency.get('competitor_count', 0)
            total_analyzed = competitive_urgency.get('total_competitors_analyzed', 0)
            urgency_str = f"""
**Structured Urgency Assessment:**
  - Level: {urgency_level}
  - Competitors with feature: {competitor_count} of {total_analyzed}
  - Assessment: {urgency_reasoning}"""
        else:
            urgency_str = "\n**Structured Urgency Assessment:** Not available"

        # Format existing categories
        categories_str = ", ".join(existing_categories) if existing_categories else "No predefined categories"

        prompt = f"""IDEA TRIAGE TASK

**Product:** {product_name} ({product_category})

**New Idea Submission:**

Title: {title}

What: {what}

Why: {why}

Use Case: {use_case}

Source: {source_type}

**Similar Ideas Found:**
{similar_ideas_str}

**Competitor Features:**
{competitors_str}
{urgency_str}

**Existing Categories in System:**
{categories_str}

**Your Task:**

1. Summarize the idea briefly (1-2 sentences)
2. Assign a category (use existing if appropriate, or suggest new)
3. Analyze the similar ideas - is this a duplicate, related, or unique?
4. Assess competitive context - USE THE STRUCTURED URGENCY ASSESSMENT ABOVE
5. Write a friendly auto-response for the customer
6. Make a recommendation (approve/merge/review/reject) with confidence and reasoning

**Important Considerations:**

- If similar ideas exist with >0.95 similarity, likely a DUPLICATE → MERGE
- USE the structured urgency level (LOW/MEDIUM/HIGH/CRITICAL) provided above
- Include the urgency_reasoning from the structured assessment in your competitive_context
- Be specific in auto-response, reference their submission
- Default to REVIEW if uncertain about approval/rejection
- Consider if the idea is actionable and clearly defined

**Required Output Format (JSON):**

You MUST return a JSON object with EXACTLY this structure:

```json
{{
  "idea_summary": "Brief 1-2 sentence summary of what the idea is",
  "category": "Category name",
  "category_confidence": 0.85,
  "similar_ideas_analysis": "Analysis of similar ideas found, or 'No similar ideas found' if none",
  "competitive_context": {{
    "competitors_with_feature": ["Competitor A", "Competitor B"],
    "competitive_urgency": "medium",
    "competitor_count": 2,
    "total_competitors_analyzed": 5,
    "urgency_reasoning": "Explanation of why this urgency level",
    "market_timing_notes": "Optional notes on market timing"
  }},
  "auto_response_text": "Thank you for submitting your idea about X. We appreciate your feedback and will review it...",
  "recommendation": {{
    "action": "review",
    "confidence": 0.75,
    "reasoning": "Why you recommend this action",
    "merge_target_id": null
  }}
}}
```

IMPORTANT:
- "competitors_with_feature" must be a LIST of strings, even if empty: []
- "recommendation" must be an OBJECT with action, confidence, reasoning fields
- "competitive_urgency" must be one of: "low", "medium", "high", "critical"
- "action" must be one of: "approve", "merge", "review", "reject"
- All confidence values are decimals between 0 and 1"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return IdeaTriageOutput

    def get_stage(self) -> str:
        return "idea_triage"

    def _normalize_output(self, output_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize LLM output to match expected schema field names.

        Handles common LLM variations:
        - 'summary' -> 'idea_summary'
        - 'auto_response' -> 'auto_response_text'
        - String recommendation -> proper dict structure
        - Empty competitor list handling
        """
        # Map alternative field names to expected names
        field_mapping = {
            'summary': 'idea_summary',
            'idea_summary': 'idea_summary',
            'auto_response': 'auto_response_text',
            'auto_response_text': 'auto_response_text',
            'response_text': 'auto_response_text',
            'customer_response': 'auto_response_text',
            'similar_ideas': 'similar_ideas_analysis',
            'similar_ideas_analysis': 'similar_ideas_analysis',
            'duplicates_analysis': 'similar_ideas_analysis',
        }

        # Apply field mappings
        normalized = {}
        for key, value in output_dict.items():
            target_key = field_mapping.get(key, key)
            normalized[target_key] = value

        # Handle recommendation if it's a string instead of dict
        if 'recommendation' in normalized:
            rec = normalized['recommendation']
            if isinstance(rec, str):
                # Convert string action to proper structure
                action = rec.lower()
                if action not in ['approve', 'merge', 'review', 'reject']:
                    action = 'review'
                normalized['recommendation'] = {
                    'action': action,
                    'confidence': 0.7,
                    'reasoning': f"LLM recommended {rec}",
                    'merge_target_id': None
                }

        # Handle competitive_context normalization
        if 'competitive_context' in normalized:
            cc = normalized['competitive_context']
            if isinstance(cc, dict):
                # Ensure competitors_with_feature is a list
                if 'competitors_with_feature' in cc:
                    cwf = cc['competitors_with_feature']
                    if isinstance(cwf, int):
                        cc['competitors_with_feature'] = []
                    elif not isinstance(cwf, list):
                        cc['competitors_with_feature'] = [str(cwf)] if cwf else []

        return normalized

    def _parse_and_validate_output(self, response_content: str) -> Dict[str, Any]:
        """
        Override base class to add output normalization before validation.
        """
        import json

        # Use parent's _extract_json method
        content = response_content.strip()

        # Check for markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end]
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end]

        content = content.strip()

        # If content still has text before JSON, find the first { or [
        if not content.startswith("{") and not content.startswith("["):
            json_start = min(
                (content.find("{") if content.find("{") != -1 else len(content)),
                (content.find("[") if content.find("[") != -1 else len(content))
            )
            if json_start < len(content):
                content = content[json_start:]

        # Parse JSON
        output_dict = json.loads(content.strip())

        # Normalize the output before validation
        normalized = self._normalize_output(output_dict)

        # Validate against Pydantic schema
        schema_class = self.get_output_schema()
        validated = schema_class(**normalized)

        # Return as dict
        return validated.model_dump(mode='json')

    def determine_triage_status(
        self,
        result: Dict[str, Any],
        auto_respond_enabled: bool = False,
        auto_respond_threshold: float = 0.9
    ) -> str:
        """
        Determine the triage status based on agent output.

        Args:
            result: The agent's triage result
            auto_respond_enabled: Whether auto-respond is enabled for the product
            auto_respond_threshold: Confidence threshold for auto-approval

        Returns one of: 'auto_approved', 'needs_review', 'duplicate', 'rejected'

        When auto_respond_enabled is False:
            - Always returns 'needs_review' so PO can review the recommendation
            - The agent's recommendation is stored but not acted upon

        When auto_respond_enabled is True:
            - Returns the appropriate status based on agent recommendation
            - 'auto_approved' if action=approve and confidence >= threshold
            - 'duplicate' if action=merge
            - 'rejected' if action=reject and confidence >= 0.7
            - 'needs_review' otherwise
        """
        # When auto-respond is OFF, always return needs_review
        # The PO will see the agent's recommendation and decide
        if not auto_respond_enabled:
            return 'needs_review'

        # Auto-respond is ON - apply the agent's recommendation
        recommendation = result.get('recommendation', {})
        action = recommendation.get('action', 'review')
        confidence = recommendation.get('confidence', 0.5)

        if action == 'merge':
            return 'duplicate'
        elif action == 'reject' and confidence >= self.REJECT_THRESHOLD:
            # Only auto-reject if we're confident
            return 'rejected' if confidence >= 0.7 else 'needs_review'
        elif action == 'approve' and confidence >= auto_respond_threshold:
            return 'auto_approved'
        else:
            return 'needs_review'
