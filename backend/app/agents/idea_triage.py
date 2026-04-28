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

from typing import Dict, Any, Type, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from app.agents.base_agent import BaseAgent

if TYPE_CHECKING:
    from app.models.idea import IdeaStatus


NOT_APPROPRIATE_KEYWORDS = [
    'off-topic', 'off topic', 'out of scope', 'not relevant',
    'unrelated to', 'inappropriate content', 'offensive',
    'spam', 'not applicable',
]


def classify_recommendation(result: Dict[str, Any]) -> "IdeaStatus":
    """Map an agent triage result to a recommended IdeaStatus.

    The agent is the arbiter. Its action + structured fields decide the status;
    deterministic similarity signals are inputs to the agent's prompt, not
    overrides on its output. Runs both during auto-execute (in
    determine_triage_status) and for the PM-facing recommendation API.

    Action semantics:
    - merge → DUPLICATE
    - approve → ACCEPTED
    - reject + existing_feature_info → FEATURE_EXISTS (agent affirmatively
      identified an existing-feature overlap)
    - reject + off-topic / offensive reasoning → NOT_APPROPRIATE (rare by design)
    - reject without either → NEEDS_REVIEW (defer to PM; the agent rejected
      but didn't identify the standard reasons)
    - review or unknown → NEEDS_REVIEW
    """
    from app.models.idea import IdeaStatus

    recommendation = result.get('recommendation', {}) or {}
    action = recommendation.get('action', 'review')
    existing_feature = result.get('existing_feature_info')
    reasoning = (recommendation.get('reasoning') or '').lower()

    if action == 'merge':
        return IdeaStatus.DUPLICATE

    if action == 'reject':
        if existing_feature:
            return IdeaStatus.FEATURE_EXISTS
        if any(kw in reasoning for kw in NOT_APPROPRIATE_KEYWORDS):
            return IdeaStatus.NOT_APPROPRIATE
        return IdeaStatus.NEEDS_REVIEW

    if action == 'approve':
        return IdeaStatus.ACCEPTED

    return IdeaStatus.NEEDS_REVIEW


class SimilarIdeaInfo(BaseModel):
    """Information about a similar idea found."""
    idea_id: int = Field(..., description="ID of the similar idea")
    title: str = Field(..., description="Title of the similar idea")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    is_duplicate: bool = Field(..., description="Whether this is considered a duplicate")


class ExistingFeatureInfo(BaseModel):
    """Information about an existing product feature that matches the idea."""
    feature_name: str = Field(..., description="Name of the existing feature")
    feature_description: str = Field(..., description="Description of the feature")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    source_url: Optional[str] = Field(None, description="URL to feature documentation if available")


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
    jtbd_statement: Optional[str] = Field(
        None,
        description="Jobs-to-be-Done: 'When [situation], I want to [motivation], so I can [outcome]'"
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
    existing_feature_info: Optional[ExistingFeatureInfo] = Field(
        None,
        description="Information about existing product feature if idea matches one"
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

5. **Existing Feature Detection**
   - The user prompt may include a deterministic similarity signal flagging an existing product feature with a high cosine-similarity match. You MUST explicitly consider this signal in your reasoning.
   - If you AGREE the idea overlaps with the existing feature, recommend REJECT and you MUST populate existing_feature_info (feature name, description, source URL if available). The classifier maps `reject + existing_feature_info` to FEATURE_EXISTS.
   - If you DISAGREE (the idea looks similar in wording but addresses a meaningfully different need), state that explicitly in your reasoning ("similar to X but different because Y") and choose APPROVE / MERGE / REVIEW as appropriate. Do NOT populate existing_feature_info in this case.
   - Never silently ignore a flagged similarity match — agree explicitly or disagree explicitly.

6. **Recommendation**
   - APPROVE: High-quality, unique idea ready for voting (confidence > 0.9)
   - MERGE: Clear duplicate of existing idea (provide merge target)
   - REJECT (Feature Exists): Idea matches an existing product feature (provide existing_feature_info)
   - REJECT: Low quality, off-topic, or clearly inappropriate (confidence < 0.5)
   - REVIEW: Needs PM review (ambiguous, sensitive, or moderate confidence)

**Decision Guidelines:**

- Default to REVIEW when uncertain
- Consider the product's current priorities and roadmap
- Weight competitive pressure appropriately
- Be generous with approval for clear, actionable ideas
- Reserve rejection for clearly problematic submissions
- If a Related Synthesis Opportunity exists with high priority, prefer APPROVE; if it has "already has linked Idea", prefer MERGE

7. **Jobs-to-be-Done Extraction**
   - Extract the underlying job the customer is hiring this feature to do
   - Format: "When [situation/circumstance], I want to [motivation/action], so I can [expected outcome/benefit]"
   - Focus on the UNDERLYING NEED, not the specific feature implementation
   - Example: Idea "Add pricing comparison table" → "When I'm evaluating software vendors for my team, I want to quickly compare pricing and feature tiers, so I can make a defensible recommendation to my manager."

**Output Requirements:**

Provide a structured analysis including:
- Brief idea summary
- JTBD statement capturing the underlying customer job
- Category assignment with confidence
- Analysis of similar ideas
- Competitive context assessment
- Auto-response for customer
- Clear recommendation with reasoning

**Reasoning Vocabulary:**

Your `reasoning` field is shown to product managers in the UI. Describe the idea's classification in user-facing terms — describe the *category* the idea falls into, not the internal action you're picking. The PM marks the idea's status themselves; do not phrase reasoning as a directive to them.

- DO write: "This duplicates an existing product feature" / "This is off-topic for the product" / "This is a duplicate of idea #42" / "This is a clear, unique enhancement worth voting on"
- DO NOT write: "Recommend REJECT" / "Recommend APPROVE" / "Mark as FEATURE_EXISTS" / "Set status to ..."
- Referencing the deterministic similarity score in your reasoning is fine when it informed your conclusion (e.g., "the 0.88 similarity match to existing feature X confirms..."). The internal `action` enum (approve/merge/review/reject) is implementation detail and should never appear in PM-facing prose.

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

        # Extract existing product feature match (new feature exists detection)
        existing_feature_match = input_data.get('existing_feature_match', {})
        if existing_feature_match and existing_feature_match.get('has_match'):
            best_match = existing_feature_match.get('best_match', {})
            feature_exists_str = f"""
**⚠️ POTENTIAL EXISTING FEATURE MATCH (similarity >= 0.85):**
  - Feature Name: {best_match.get('feature_name', 'Unknown')}
  - Description: {best_match.get('feature_description', '')}
  - Similarity Score: {best_match.get('similarity_score', 0):.2f}
  - Source: {best_match.get('source_url') or 'N/A'}

  This is an embedding similarity signal — high textual overlap, but YOUR JUDGMENT decides
  whether the idea actually duplicates this feature.
  - If you AGREE it duplicates: recommend REJECT and populate existing_feature_info.
  - If you DISAGREE (similar wording, different need): state explicitly in reasoning
    why it's different and choose APPROVE / MERGE / REVIEW accordingly. Do NOT populate
    existing_feature_info.
  - Never silently ignore this signal."""
        else:
            feature_exists_str = ""

        # Format related synthesis opportunities — opportunities the team has
        # already identified that overlap with this idea.
        related_opps = input_data.get('related_synthesis_opportunities') or []
        if related_opps:
            opp_lines = []
            for o in related_opps:
                score = o.get('priority_score')
                score_str = f"{score:.0f}" if isinstance(score, (int, float)) else "N/A"
                linked = " (already has linked Idea)" if o.get('has_linked_idea') else ""
                tier = o.get('investment_tier') or "?"
                opp_lines.append(
                    f"  - [Opp #{o.get('opportunity_id')}] {o.get('opportunity_name')} "
                    f"(priority: {score_str}, tier: {tier}){linked}"
                )
            related_opps_str = "\n**Related Synthesis Opportunities (team-identified):**\n" + "\n".join(opp_lines)
        else:
            related_opps_str = ""

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
{feature_exists_str}
{related_opps_str}

**Existing Categories in System:**
{categories_str}

**Your Task:**

1. Summarize the idea briefly (1-2 sentences)
2. Assign a category (use existing if appropriate, or suggest new)
3. Analyze the similar ideas - is this a duplicate, related, or unique?
4. Assess competitive context - USE THE STRUCTURED URGENCY ASSESSMENT ABOVE
5. Check for EXISTING PRODUCT FEATURE - if detected above, include existing_feature_info
6. Write a CONCISE auto-response for the customer (MUST be under 100 words)
7. Make a recommendation (approve/merge/review/reject) with confidence and reasoning

**Important Considerations:**

- If EXISTING PRODUCT FEATURE DETECTED above → recommend REJECT and include existing_feature_info
- If similar ideas exist with >0.95 similarity, likely a DUPLICATE → MERGE
- USE the structured urgency level (LOW/MEDIUM/HIGH/CRITICAL) provided above
- Include the urgency_reasoning from the structured assessment in your competitive_context
- Auto-response MUST be concise (under 100 words): thank them briefly, acknowledge their idea, mention next steps
- Default to REVIEW if uncertain about approval/rejection
- Consider if the idea is actionable and clearly defined

**Required Output Format (JSON):**

You MUST return a JSON object with EXACTLY this structure:

```json
{{
  "idea_summary": "Brief 1-2 sentence summary of what the idea is",
  "jtbd_statement": "When [situation], I want to [motivation], so I can [outcome]",
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
  "existing_feature_info": null,
  "auto_response_text": "Thanks for your idea about X! We've received it and our team will review it shortly. We'll keep you posted on next steps.",
  "recommendation": {{
    "action": "review",
    "confidence": 0.75,
    "reasoning": "Why you recommend this action",
    "merge_target_id": null
  }}
}}
```

If an EXISTING PRODUCT FEATURE was detected, include existing_feature_info like this:
```json
"existing_feature_info": {{
  "feature_name": "Name of existing feature",
  "feature_description": "Description of the existing feature",
  "similarity_score": 0.92,
  "source_url": "https://example.com/feature-docs"
}}
```

IMPORTANT:
- "competitors_with_feature" must be a LIST of strings, even if empty: []
- "recommendation" must be an OBJECT with action, confidence, reasoning fields
- "competitive_urgency" must be one of: "low", "medium", "high", "critical"
- "action" must be one of: "approve", "merge", "review", "reject"
- "existing_feature_info" should be null if no match, or an OBJECT if feature exists
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
        auto_respond_threshold: float = 0.9,
    ) -> "IdeaStatus":
        """Decide the idea.status to write, gating auto-execute behind threshold.

        Two-layer model:
        - Layer 1 (classify_recommendation, module-level): map agent output to
          a recommended IdeaStatus. The agent is the arbiter — deterministic
          signals are inputs to its prompt, not overrides on its output.
        - Layer 2 (this method): when auto-respond is enabled, execute the
          recommended status if confidence clears the threshold; otherwise
          hold for PM review. When auto-respond is disabled, always
          NEEDS_REVIEW (the agent's classified recommendation is still
          stored and surfaced via the recommendation API).

        DUPLICATE is unconditional once auto-respond is on because the merge
        target ID itself is a deterministic check. All other classified
        statuses (ACCEPTED, FEATURE_EXISTS, NOT_APPROPRIATE) gate behind
        auto_respond_threshold.
        """
        from app.models.idea import IdeaStatus

        recommended = classify_recommendation(result)

        if not auto_respond_enabled:
            return IdeaStatus.NEEDS_REVIEW

        if recommended == IdeaStatus.NEEDS_REVIEW:
            return IdeaStatus.NEEDS_REVIEW

        if recommended == IdeaStatus.DUPLICATE:
            return IdeaStatus.DUPLICATE

        confidence = (result.get('recommendation') or {}).get('confidence', 0.5)
        if confidence >= auto_respond_threshold:
            return recommended
        return IdeaStatus.NEEDS_REVIEW
