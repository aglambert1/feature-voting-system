"""
Competitor Functional Audit Agent.

This agent performs a detailed functional audit of a single competitor,
comparing their capabilities against our product through the lens of
Jobs-to-be-Done (JTBD) framework when a job map is available, or
falling back to feature-centric analysis when it is not.

The agent uses an external prompt template (Competitor_Functional_Audit_Prompt.md)
for flexibility in production environments.
"""

import json
from typing import Dict, Any, Type, List, Literal, Optional

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.schemas.competitive_reports import (
    FunctionalAuditOutput,
    FunctionalAuditStage1Output,
    FunctionalAuditStage2Output,
)
from app.services.prompt_loader import get_prompt_loader
from app.services.html_cleaner import get_html_cleaner
from app.services.search_service import get_search_service


# Staged execution modes. "full" preserves the pre-split single-call behavior
# and remains the default so any caller not opting into staging is unaffected.
AuditStage = Literal["full", "stage1", "stage2"]


class CompetitorFunctionalAuditAgent(BaseAgent):
    """
    Per-competitor functional audit agent.

    When a job map is provided, analyzes a single competitor through JTBD:
    - Competitor context (positioning, differentiation, target customer)
    - Job assessments (scores, features, outcome coverage per job)
    - Functional comparison table with job linkage
    - Technical constraints

    When no job map is provided, falls back to feature-centric analysis:
    - Competitor context
    - Functional comparison table (Parity/Advantage/Gap/Differentiator)
    - Deep-dive on gaps
    - Technical constraints

    When web search is available, the agent can research the competitor
    directly — searching for features, pricing, integrations, and reviews.

    Usage:
        agent = CompetitorFunctionalAuditAgent(db=db, llm_service=llm_service)
        result = agent.execute({
            'competitor_name': 'Acme Corp',
            'competitor_url': 'https://acme.com',
            'product_context': {...},  # Our product info
            'job_map': {...},          # Optional: JTBD job map
            'target_customer_profile': {...},  # Optional: target customer
        })
    """

    PROMPT_FILENAME = "Competitor_Functional_Audit_Prompt.md"

    def __init__(
        self,
        *args,
        web_research_enabled: bool = True,
        stage: AuditStage = "full",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.search_service = get_search_service()
        self.web_research_enabled = web_research_enabled
        self.stage: AuditStage = stage

    def execute_stage_1(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Run Stage 1 (context + comparison + technical_constraints).

        Temporarily flips `self.stage` to "stage1" so `get_output_schema`,
        `get_system_prompt`, and `build_user_prompt` all produce Stage 1 variants.
        Restores the previous stage after execution so the agent can be reused.
        """
        previous_stage = self.stage
        self.stage = "stage1"
        try:
            return self.execute(input_data, **kwargs)
        finally:
            self.stage = previous_stage

    def execute_stage_2(
        self, input_data_with_stage_1_output: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Run Stage 2 (job_assessments + evidence_citations + gaps_deep_dive).

        `input_data_with_stage_1_output` must include `stage_1_output` — the
        dict produced by `execute_stage_1`. The prompt renders it as conditioning
        context so the agent doesn't re-derive Stage 1 content.
        """
        previous_stage = self.stage
        self.stage = "stage2"
        try:
            return self.execute(input_data_with_stage_1_output, **kwargs)
        finally:
            self.stage = previous_stage

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

    def get_stage(self) -> str:
        """Return the pipeline stage for this agent.

        When running staged (stage1/stage2), disambiguate the log entries so
        each LLM call's token usage and latency can be attributed correctly.
        """
        if self.stage == "stage1":
            return "functional_audit_stage1"
        if self.stage == "stage2":
            return "functional_audit_stage2"
        return "functional_audit"

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the Pydantic schema for output validation.

        Staged execution returns a narrower schema per stage. Callers that
        don't opt into staging (stage="full") see the unchanged FunctionalAuditOutput.
        """
        if self.stage == "stage1":
            return FunctionalAuditStage1Output
        if self.stage == "stage2":
            return FunctionalAuditStage2Output
        return FunctionalAuditOutput

    def get_system_prompt(self) -> str:
        """Route to the right system prompt variant for the current stage."""
        if self.stage == "stage1":
            return self._build_stage1_system_prompt()
        if self.stage == "stage2":
            return self._build_stage2_system_prompt()
        return self._build_full_system_prompt()

    def _build_full_system_prompt(self) -> str:
        """
        Build system prompt with JTBD framework and JSON output instructions.

        When a job map is available, the agent uses JTBD as its analytical lens.
        When no job map is provided, it falls back to feature-centric analysis.
        """
        has_search = self.web_research_enabled and self.search_service.is_available()

        search_section = ""
        if has_search:
            search_section = """
## Research Strategy

You have access to a web_search tool. Use it to gather comprehensive, current information:
1. Search "[competitor] features" for official feature lists
2. Search "[competitor] pricing plans" for pricing model and tier details
3. Search "[competitor] integrations" for ecosystem/connectivity
4. Search "[competitor] vs [our product]" for direct comparison perspectives
5. Search "[competitor] reviews G2" for real user feedback on capabilities

Make 3-5 targeted searches to supplement any pre-provided data. Cross-reference
web results with provided evidence for accuracy.
"""

        return f"""You are a Product Strategist applying Clayton Christensen's Jobs-to-be-Done (JTBD) framework to competitive analysis.

Your task is to evaluate how well a competitor product serves the customer jobs defined in the product's job map, compared to our product.

## Framework
Products compete on how well they help customers make progress on specific jobs. Features are the mechanism — jobs are the analytical lens.

## When a Job Map is provided
For each job in the map:
1. Score our product 1-10 on how well it serves this job
2. Score the competitor 1-10 on how well they serve this job
3. Explain what drives the score difference
4. List features from BOTH products that contribute (advantages AND gaps in one view)
5. Assess coverage of each desired outcome

## When no Job Map is provided
Fall back to feature-centric analysis: identify features, categorize as Parity/Advantage/Gap/Differentiator.

## Evidence Integration
When evidence is provided, use it to INFORM your assessments. Cite evidence by ID when it influences a finding. Evidence from the product team is curated and high-confidence.

## Scoring Principles (1-10 scale)
- 9-10: Best-in-class, fully addresses the job with excellent UX
- 7-8: Strong coverage, minor gaps in desired outcomes
- 5-6: Adequate but notable missing capabilities
- 3-4: Minimal coverage, significant gaps
- 1-2: Barely addresses the job
{search_section}
## Output Format

You MUST respond with a valid JSON object matching this exact structure:

```json
{{{{
  "competitor_context": {{{{
    "positioning": "Their hero message and self-description",
    "core_differentiation": "What makes them unique",
    "target_customer": "Their ideal customer profile",
    "key_features": ["Feature 1", "Feature 2", "Feature 3", "Feature 4", "Feature 5"]
  }}}},
  "functional_comparison": [
    {{{{
      "feature_category": "Category name",
      "competitor_feature_name": "Feature name",
      "functional_description": "What it actually does",
      "mapping_status": "Gap",
      "job_id": "j1 or null if no job map"
    }}}}
  ],
  "job_assessments": [
    {{{{
      "job_id": "j1",
      "job_statement": "When I need to..., I want to..., so I can...",
      "importance": "critical",
      "our_score": 7,
      "competitor_score": 8,
      "score_rationale": "Explanation of what drives the score difference",
      "features": [
        {{{{
          "feature_name": "Feature A",
          "description": "What it does functionally",
          "whose": "ours",
          "position": "advantage",
          "evidence_ids": [5]
        }}}},
        {{{{
          "feature_name": "Feature X",
          "description": "What it does functionally",
          "whose": "theirs",
          "position": "gap",
          "evidence_ids": [12]
        }}}}
      ],
      "outcome_coverage": [
        {{{{
          "desired_outcome": "Minimize time to complete X",
          "our_coverage": "full",
          "competitor_coverage": "partial"
        }}}}
      ]
    }}}}
  ],
  "gaps_deep_dive": [
    {{{{
      "feature_name": "Feature name",
      "user_problem": "Pain point this solves",
      "evidence": "Quote or description proving value"
    }}}}
  ],
  "evidence_citations": [
    {{{{
      "evidence_id": 5,
      "finding_type": "job_score",
      "finding_description": "How this evidence informed the assessment"
    }}}}
  ],
  "technical_constraints": {{{{
    "integrations": ["Integration 1", "Integration 2"],
    "api_capabilities": "API description or null",
    "platform_requirements": "Platform requirements or null",
    "additional_notes": "Other notes or null"
  }}}}
}}}}
```

**When a job map IS provided:** Include `job_assessments` and `evidence_citations`. The `gaps_deep_dive` can be empty or omitted.
**When NO job map is provided:** Include `gaps_deep_dive`. The `job_assessments` and `evidence_citations` can be empty or omitted.

## Mapping Status Definitions

- **Parity**: Functionality exists in both products with similar depth
- **Advantage**: We have this feature; they do not
- **Gap**: They have this feature; we do not
- **Differentiator**: A unique feature they offer that significantly alters user workflow

## Important Guidelines

1. Identify 15-25 features for comprehensive coverage
2. Use standard categories: Core Functionality, UX/UI, Integrations, Security/Compliance, AI/Automation, Reporting/Analytics, Administration, Mobile, Collaboration
3. Be specific: "AI-powered receipt scanning with OCR" not just "AI features"
4. Focus on Gaps and Differentiators — these are most valuable for product strategy
5. Include integration ecosystem in technical_constraints
6. Output ONLY valid JSON — no markdown code blocks, no explanatory text
7. Ensure all strings are properly escaped and the JSON is complete"""

    def _build_stage1_system_prompt(self) -> str:
        """Stage 1 of the staged audit: context + comparison + technical_constraints only.

        Smaller output target (~4-6k tokens) so this stage completes in ~45s.
        Deliberately excludes job_assessments, evidence_citations, and gaps_deep_dive —
        those are Stage 2's job.
        """
        has_search = self.web_research_enabled and self.search_service.is_available()

        search_section = ""
        if has_search:
            search_section = """
## Research Strategy

You have access to a web_search tool. Use 3-5 targeted searches on the
competitor (features, pricing, integrations, reviews) to supplement any
pre-provided data. Cross-reference web results with provided evidence.
"""

        return f"""You are a Product Strategist applying Jobs-to-be-Done (JTBD) to competitive analysis.

This is STAGE 1 of a two-stage audit. In this stage you produce ONLY these sections:
- competitor_context (positioning, core_differentiation, target_customer, key_features)
- functional_comparison (15-25 feature rows with Parity/Advantage/Gap/Differentiator)
- technical_constraints (integrations, api_capabilities, platform_requirements, additional_notes)

DO NOT produce job_assessments, evidence_citations, or gaps_deep_dive — those are produced
in Stage 2 using your Stage 1 output as conditioning context.
{search_section}
## Output Format

Respond with a valid JSON object matching this exact structure (and nothing else):

```json
{{{{
  "competitor_context": {{{{
    "positioning": "Their hero message",
    "core_differentiation": "What makes them unique",
    "target_customer": "Their ICP",
    "key_features": ["Feature 1", "Feature 2", "Feature 3", "Feature 4", "Feature 5"]
  }}}},
  "functional_comparison": [
    {{{{
      "feature_category": "Category",
      "competitor_feature_name": "Feature name",
      "functional_description": "What it actually does",
      "mapping_status": "Gap",
      "job_id": "j1 or null if no job map"
    }}}}
  ],
  "technical_constraints": {{{{
    "integrations": ["Integration 1", "Integration 2"],
    "api_capabilities": "API description or null",
    "platform_requirements": "Platform requirements or null",
    "additional_notes": "Other notes or null"
  }}}}
}}}}
```

## Mapping Status Definitions
- Parity: both have similar capability
- Advantage: we have / they don't
- Gap: they have / we don't
- Differentiator: unique workflow they offer

## Guidelines
1. 15-25 features for comprehensive coverage
2. Use standard categories: Core Functionality, UX/UI, Integrations, Security/Compliance, AI/Automation, Reporting/Analytics, Administration, Mobile, Collaboration
3. Be specific: "AI-powered receipt scanning with OCR" not just "AI features"
4. Focus on Gaps and Differentiators — these are most valuable for product strategy
5. If a job map IS provided, link each feature to its most relevant `job_id` in the comparison row
6. Output ONLY valid JSON — no markdown code blocks, no explanatory text
7. Ensure all strings are properly escaped and the JSON is complete"""

    def _build_stage2_system_prompt(self) -> str:
        """Stage 2 of the staged audit: job_assessments + evidence_citations + gaps_deep_dive.

        Stage 1 output is passed into the user prompt as conditioning context so
        this stage doesn't re-derive positioning/comparison — it analyzes the job map
        using Stage 1's feature set.
        """
        return """You are a Product Strategist applying Jobs-to-be-Done (JTBD) to competitive analysis.

This is STAGE 2 of a two-stage audit. Stage 1 (competitor_context + functional_comparison +
technical_constraints) is already complete and will be provided in the user prompt as
conditioning context. In this stage you produce ONLY these sections:
- job_assessments (one per job in the job map; features[] with position=advantage/gap/parity/differentiator)
- evidence_citations (link evidence IDs to specific findings)
- gaps_deep_dive (ONLY if no job map is provided)

Do NOT restate or modify Stage 1 output — use it as given.

## Scoring Principles (1-10 scale)
- 9-10: Best-in-class, fully addresses the job with excellent UX
- 7-8: Strong coverage, minor gaps in desired outcomes
- 5-6: Adequate but notable missing capabilities
- 3-4: Minimal coverage, significant gaps
- 1-2: Barely addresses the job

## Evidence Integration
When evidence is provided, cite `evidence_ids` in `features[]` and populate `evidence_citations`
linking evidence to specific findings. Evidence from the product team is high-confidence.

## Output Format

Respond with a valid JSON object matching this exact structure (and nothing else):

```json
{{
  "job_assessments": [
    {{
      "job_id": "j1",
      "job_statement": "When I need to..., I want to..., so I can...",
      "importance": "critical",
      "our_score": 7,
      "competitor_score": 8,
      "score_rationale": "Explanation of what drives the score difference",
      "features": [
        {{
          "feature_name": "Feature A",
          "description": "What it does functionally",
          "whose": "ours",
          "position": "advantage",
          "evidence_ids": [5]
        }}
      ],
      "outcome_coverage": [
        {{"desired_outcome": "Minimize time to complete X", "our_coverage": "full", "competitor_coverage": "partial"}}
      ]
    }}
  ],
  "evidence_citations": [
    {{"evidence_id": 5, "finding_type": "job_score", "finding_description": "How this evidence informed the assessment"}}
  ],
  "gaps_deep_dive": [
    {{"feature_name": "Feature name", "user_problem": "Pain point", "evidence": "Quote from documentation"}}
  ]
}}
```

## When a Job Map IS provided
- Produce one job_assessment per job in the map
- `features[]` draws from Stage 1's functional_comparison — tag each with position
- `outcome_coverage` assesses each desired_outcome
- `gaps_deep_dive` MAY be empty

## When NO Job Map is provided
- `job_assessments` and `evidence_citations` MAY be empty
- Populate `gaps_deep_dive` for each feature flagged as `Gap` in Stage 1

## Guidelines
1. Pull feature names directly from Stage 1's functional_comparison when possible
2. Stay anchored in Stage 1 — don't contradict the mapping_status or invent new features
3. Output ONLY valid JSON — no markdown code blocks, no explanatory text
4. Ensure all strings are properly escaped and the JSON is complete"""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        Build the user prompt with competitor data and optional job map.

        Args:
            input_data: Must contain:
                - competitor_name: Name of competitor
                - competitor_url: URL of competitor
                - product_context: Dict with our product info
                - web_search_results: List of search result dicts OR pre-formatted string
                Optional:
                - job_map: Dict with jobs list and metadata
                - target_customer_profile: Dict with persona info
                - user_provided_evidence: List of evidence dicts
        """
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        product_context = input_data.get('product_context', {})
        web_search_results = input_data.get('web_search_results', [])
        user_provided_evidence = input_data.get('user_provided_evidence', [])
        fetched_sources = input_data.get('fetched_sources', [])
        job_map = input_data.get('job_map')
        target_customer_profile = input_data.get('target_customer_profile')

        has_job_map = bool(
            job_map and (
                job_map.get('jobs')
                or job_map.get('functional_jobs')
                or job_map.get('emotional_jobs')
                or job_map.get('social_jobs')
            )
        )

        # Format product context (includes target customer if available)
        product_info = self._format_product_context(
            product_context, target_customer_profile
        )

        # Format job map section
        job_map_section = self._format_job_map(job_map) if has_job_map else ""

        # Format search results (clean HTML if needed)
        search_content = self._format_search_results(web_search_results)

        # Format fetched source pages (from user-supplied source_urls)
        fetched_sources_content = self._format_fetched_sources(fetched_sources)

        # Format user-provided evidence (grouped by job if job map exists)
        evidence_content = self._format_user_evidence(
            user_provided_evidence, job_map
        )

        # Try to load external prompt template for additional context
        prompt_loader = get_prompt_loader()
        try:
            external_prompt = prompt_loader.load_prompt(self.PROMPT_FILENAME)
            task_context = self._extract_task_context(external_prompt)
        except FileNotFoundError:
            task_context = ""

        # Add search instructions if available
        search_instructions = ""
        if self.web_research_enabled and self.search_service.is_available():
            search_instructions = f"""
## Web Research Instructions
Use the web_search tool to gather additional information about {competitor_name}. Suggested searches:
1. "{competitor_name} features" — official feature list
2. "{competitor_name} pricing" — pricing tiers and plans
3. "{competitor_name} integrations" — ecosystem connections
4. "{competitor_name} reviews" — user perspectives
Cross-reference web results with any pre-provided data below.
"""

        # Build analysis mode instruction — varies by stage and whether job map is present.
        if self.stage == "stage1":
            analysis_instruction = f"""## Your Task (Stage 1 of 2)

Produce ONLY Stage 1 output for {competitor_name}:
- competitor_context
- functional_comparison (15-25 rows, each linked to a job_id if the job map is above)
- technical_constraints

DO NOT produce job_assessments, evidence_citations, or gaps_deep_dive — those are Stage 2.

Respond with ONLY a valid JSON object following the Stage 1 schema."""
        elif self.stage == "stage2":
            if has_job_map:
                analysis_instruction = f"""## Your Task (Stage 2 of 2)

Stage 1 output is provided above as ## Stage 1 Context (already produced). Use it as given.

Now produce Stage 2 analysis for {competitor_name}:
- For EACH job in the job map above, produce a job_assessment with scores for our product and the competitor
- Pull features from Stage 1's functional_comparison where relevant — tag each with position
- Cite evidence_ids where they inform your finding
- Populate evidence_citations linking evidence to specific findings

Respond with ONLY a valid JSON object following the Stage 2 schema.
Populate `job_assessments` and `evidence_citations`. `gaps_deep_dive` may be empty."""
            else:
                analysis_instruction = f"""## Your Task (Stage 2 of 2)

Stage 1 output is provided above as ## Stage 1 Context (already produced). Use it as given.

No job map is available — use feature-centric analysis.
For each feature marked as "Gap" in Stage 1's functional_comparison, produce a gaps_deep_dive entry.

Respond with ONLY a valid JSON object following the Stage 2 schema.
Populate `gaps_deep_dive`. `job_assessments` and `evidence_citations` may be empty."""
        elif has_job_map:
            analysis_instruction = f"""## Your Task

Analyze {competitor_name} through the JTBD lens using the job map provided above.
For EACH job in the map, produce a job assessment with scores for both our product and the competitor.
Also produce a functional comparison table linking each feature to its relevant job ID.
Cite evidence by ID where it informs your assessment.

Respond with ONLY a valid JSON object following the schema in the system prompt.
Include `job_assessments` and `evidence_citations` in your response."""
        else:
            analysis_instruction = f"""## Your Task

No job map is available. Use feature-centric analysis.
Analyze {competitor_name} and produce a comprehensive functional audit report.
Focus on identifying their actual capabilities, not marketing claims.
Aim for 15-25 features across all categories for thorough coverage.
For each feature gap identified, provide evidence of its value.

Respond with ONLY a valid JSON object following the schema in the system prompt.
Include `gaps_deep_dive` in your response."""

        # For Stage 2, prepend the Stage 1 output as conditioning context so the
        # agent can anchor its analysis without re-deriving Stage 1 content.
        stage_1_context = ""
        if self.stage == "stage2":
            stage_1_output = input_data.get("stage_1_output")
            if stage_1_output is not None:
                stage_1_context = (
                    "\n## Stage 1 Context (already produced — use as given)\n\n"
                    f"```json\n{json.dumps(stage_1_output, indent=2)}\n```\n"
                )

        prompt = f"""# Competitor Analysis Request

## Competitor Information
- **Name:** {competitor_name}
- **URL:** {competitor_url}

## Our Product Context
{product_info}
{job_map_section}
{search_instructions}
## Competitor Source Data
{search_content}
{fetched_sources_content}
{evidence_content}
{stage_1_context}
{task_context}

{analysis_instruction}"""

        return prompt

    def build_concise_user_prompt(self, input_data: Dict[str, Any]) -> Optional[str]:
        """Build a concise prompt for truncation recovery.

        Preserves all source data (competitor info, product context, search results,
        fetched sources, evidence) — the previous response was truncated because
        the OUTPUT was too long, so we tighten output constraints while keeping
        inputs intact.
        """
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        product_context = input_data.get('product_context', {})
        web_search_results = input_data.get('web_search_results', [])
        fetched_sources = input_data.get('fetched_sources', [])
        user_provided_evidence = input_data.get('user_provided_evidence', [])
        job_map = input_data.get('job_map')
        target_customer_profile = input_data.get('target_customer_profile')

        has_job_map = bool(
            job_map and (
                job_map.get('jobs')
                or job_map.get('functional_jobs')
                or job_map.get('emotional_jobs')
                or job_map.get('social_jobs')
            )
        )

        product_info = self._format_product_context(product_context, target_customer_profile)
        job_map_section = self._format_job_map(job_map) if has_job_map else ""
        search_content = self._format_search_results(web_search_results)
        fetched_sources_content = self._format_fetched_sources(fetched_sources)
        evidence_content = self._format_user_evidence(user_provided_evidence, job_map)

        if has_job_map:
            limits = (
                "1. functional_comparison: MAX 15 rows. Pick most strategically important.\n"
                "2. job_assessments: one per job in the job map. features[] MAX 5 per job. "
                "evidence_citations MAX 3 per job. MAX 10 words per evaluation field.\n"
                "3. technical_constraints: MAX 5 items per sub-list.\n"
            )
        else:
            limits = (
                "1. functional_comparison: MAX 15 rows.\n"
                "2. gaps_deep_dive: MAX 5 entries. MAX 15 words per field.\n"
                "3. technical_constraints: MAX 5 items per sub-list.\n"
            )

        return f"""# Competitor Analysis Request (CONCISE RECOVERY)

CRITICAL CONSTRAINT: A previous analysis was cut off because the response was too long.
You MUST follow these HARD LIMITS exactly:

{limits}
4. No markdown, no explanatory text — raw JSON only.

## Competitor Information
- **Name:** {competitor_name}
- **URL:** {competitor_url}

## Our Product Context
{product_info}
{job_map_section}
## Competitor Source Data
{search_content}
{fetched_sources_content}
{evidence_content}

Respond with ONLY a valid JSON object following the schema in the system prompt.
Return ONLY the JSON object."""

    def _format_product_context(
        self,
        product_context: Dict[str, Any],
        target_customer_profile: Dict[str, Any] = None,
    ) -> str:
        """Format our product context for the prompt, including target customer."""
        if not product_context:
            return "No product context provided."

        parts = []

        if product_context.get('product_name'):
            parts.append(f"**Product Name:** {product_context['product_name']}")

        if product_context.get('product_category'):
            parts.append(f"**Category:** {product_context['product_category']}")

        # Add target customer profile if available
        if target_customer_profile:
            persona = target_customer_profile.get('persona_name', '')
            company = target_customer_profile.get('company_characteristics', '')
            if persona and company:
                parts.append(f"**Target Customer:** {persona}: {company}")
            elif persona:
                parts.append(f"**Target Customer:** {persona}")
            elif company:
                parts.append(f"**Target Customer:** {company}")

        if product_context.get('core_features'):
            features = product_context['core_features']
            if isinstance(features, list):
                feature_list = "\n".join(f"  - {f}" for f in features[:10])
                parts.append(f"**Our Core Features:**\n{feature_list}")

        if product_context.get('target_users'):
            parts.append(f"**Target Users:** {product_context['target_users']}")

        if product_context.get('description'):
            parts.append(f"**Description:** {product_context['description']}")

        return "\n".join(parts) if parts else "No product context provided."

    def _format_job_map(self, job_map: Dict[str, Any]) -> str:
        """Format the JTBD job map for the prompt.

        Supports two structures:
        1. Flat: {'jobs': [...]}
        2. Hierarchical: {'main_job', 'functional_jobs': [...], 'emotional_jobs': [...], 'social_jobs': [...]}
        """
        if not job_map:
            return ""

        # Collect all jobs from either structure
        all_jobs = []
        if job_map.get('jobs'):
            all_jobs = list(job_map['jobs'])
        else:
            # Hierarchical structure
            all_jobs.extend(job_map.get('functional_jobs', []) or [])
            all_jobs.extend(job_map.get('emotional_jobs', []) or [])
            all_jobs.extend(job_map.get('social_jobs', []) or [])

        if not all_jobs:
            return ""

        parts = [
            "",
            "## Customer Job Map",
            "",
        ]

        if job_map.get('main_job'):
            parts.append(f"**Main Job:** {job_map['main_job']}")
            parts.append("")

        if job_map.get('target_customer'):
            parts.append(f"**Target Customer:** {job_map['target_customer']}")
            parts.append("")

        parts.append("### Jobs to Evaluate")
        parts.append("")

        for job in all_jobs:
            job_id = job.get('job_id', 'unknown')
            job_type = job.get('job_type', '')
            statement = job.get('statement', '')
            importance = job.get('importance', '')

            type_label = f" ({job_type})" if job_type else ""
            importance_label = f" [Importance: {importance}]" if importance else ""

            parts.append(
                f"- **{job_id}{type_label}:** "
                f"{statement}{importance_label}"
            )

            # Add desired outcomes if present
            outcomes = job.get('desired_outcomes', [])
            if outcomes:
                for outcome in outcomes:
                    if isinstance(outcome, dict):
                        parts.append(
                            f"  - Outcome: {outcome.get('outcome', outcome)}"
                        )
                    else:
                        parts.append(f"  - Outcome: {outcome}")

        parts.append("")
        return "\n".join(parts)

    def _format_search_results(self, results: Any) -> str:
        """
        Format web search results for the prompt.

        Handles:
        - List of search result dicts (cleans HTML)
        - Pre-formatted string (uses as-is)
        - Empty/None (returns placeholder)
        """
        if not results:
            return "No web search results available. Analyze based on general knowledge."

        # If already a string, use as-is
        if isinstance(results, str):
            return results

        # If list of dicts, clean and format
        if isinstance(results, list):
            html_cleaner = get_html_cleaner()
            return html_cleaner.clean_search_results(results)

        return "No web search results available. Analyze based on general knowledge."

    def _format_fetched_sources(self, fetched_sources: list) -> str:
        """Format pages fetched from user-supplied source_urls.

        Each entry is a dict with {url, title, text}. Rendered as a
        '## Fetched Source Pages' block so the agent treats them as
        authoritative alongside (or instead of) web search results.
        """
        if not fetched_sources:
            return ""

        parts = [
            "",
            "## Fetched Source Pages",
            "",
            "The following pages were explicitly provided by the caller. "
            "Treat this content as authoritative.",
            "",
        ]

        for src in fetched_sources:
            url = src.get('url', '')
            title = src.get('title', '') or url or 'Untitled'
            text = src.get('text', '') or ''
            parts.append(f"### {title}")
            if url:
                parts.append(f"**URL:** {url}")
            parts.append("")
            parts.append(text)
            parts.append("")

        return "\n".join(parts)

    def _format_user_evidence(
        self,
        evidence_list: list,
        job_map: Dict[str, Any] = None,
    ) -> str:
        """Format user-provided evidence records for the prompt.

        When a job map is available, groups evidence by the most relevant job
        using keyword matching on evidence titles and content against job
        statements and desired outcomes.

        Always includes evidence IDs so the agent can cite them.
        """
        if not evidence_list:
            return ""

        has_jobs = bool(
            job_map and (
                job_map.get('jobs')
                or job_map.get('functional_jobs')
                or job_map.get('emotional_jobs')
                or job_map.get('social_jobs')
            )
        )

        if has_jobs:
            return self._format_evidence_by_job(evidence_list, job_map)

        # Flat evidence list (no job map)
        parts = [
            "## Evidence (cite by ID in your assessment)",
            "",
            "The following evidence was curated by the product team. "
            "Treat this as high-confidence information.",
            "",
        ]

        for ev in evidence_list:
            ev_id = ev.get('id', ev.get('evidence_id', '?'))
            title = ev.get('title', 'Untitled')
            content = ev.get('content', '')
            ev_type = ev.get('evidence_type', 'unknown')
            source_url = ev.get('source_url', '')
            source_desc = ev.get('source_description', '')

            parts.append(f"### [ID: {ev_id}] {title}")
            parts.append(f"**Type:** {ev_type}")
            if source_desc:
                parts.append(f"**Source:** {source_desc}")
            if source_url:
                parts.append(f"**URL:** {source_url}")
            parts.append("")
            parts.append(content)
            parts.append("")

        return "\n".join(parts)

    def _format_evidence_by_job(
        self,
        evidence_list: list,
        job_map: Dict[str, Any],
    ) -> str:
        """Group evidence by most relevant job using keyword overlap.

        Simple heuristic: tokenize job statement + outcomes into keywords,
        then check overlap with evidence title + content. Assign to best
        matching job, or 'unassigned' if no overlap.
        """
        # Support both flat ('jobs') and hierarchical (functional/emotional/social) structures
        jobs = []
        if job_map.get('jobs'):
            jobs = list(job_map['jobs'])
        else:
            jobs.extend(job_map.get('functional_jobs', []) or [])
            jobs.extend(job_map.get('emotional_jobs', []) or [])
            jobs.extend(job_map.get('social_jobs', []) or [])

        # Build keyword sets for each job
        job_keywords = {}
        for job in jobs:
            job_id = job.get('job_id', 'unknown')
            words = set()
            statement = job.get('statement', '').lower()
            words.update(w for w in statement.split() if len(w) > 3)
            for outcome in job.get('desired_outcomes', []):
                text = outcome.get('outcome', outcome) if isinstance(outcome, dict) else str(outcome)
                words.update(w for w in text.lower().split() if len(w) > 3)
            job_keywords[job_id] = words

        # Build job statement lookup for display
        job_statements = {
            job.get('job_id', 'unknown'): job.get('statement', '')
            for job in jobs
        }

        # Assign each evidence to best matching job
        assigned: Dict[str, list] = {job.get('job_id', 'unknown'): [] for job in jobs}
        unassigned = []

        for ev in evidence_list:
            ev_text = (
                (ev.get('title', '') + ' ' + ev.get('content', ''))
                .lower()
            )
            ev_words = set(w for w in ev_text.split() if len(w) > 3)

            best_job = None
            best_overlap = 0
            for job_id, keywords in job_keywords.items():
                overlap = len(ev_words & keywords)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_job = job_id

            if best_job and best_overlap > 0:
                assigned[best_job].append(ev)
            else:
                unassigned.append(ev)

        # Format output
        parts = [
            "## Evidence (cite by ID in your assessment)",
            "",
            "The following evidence was curated by the product team. "
            "Treat this as high-confidence information.",
            "",
        ]

        for job_id in assigned:
            if not assigned[job_id]:
                continue
            statement = job_statements.get(job_id, '')
            parts.append(f'### Evidence for Job {job_id}: "{statement}"')
            parts.append("")
            for ev in assigned[job_id]:
                ev_id = ev.get('id', ev.get('evidence_id', '?'))
                title = ev.get('title', 'Untitled')
                content = ev.get('content', '')
                # Truncate content for summary line
                summary = content[:200] + '...' if len(content) > 200 else content
                parts.append(f"- **[ID: {ev_id}]** {title} — {summary}")
            parts.append("")

        if unassigned:
            parts.append("### Unassigned Evidence")
            parts.append("")
            for ev in unassigned:
                ev_id = ev.get('id', ev.get('evidence_id', '?'))
                title = ev.get('title', 'Untitled')
                content = ev.get('content', '')
                summary = content[:200] + '...' if len(content) > 200 else content
                parts.append(f"- **[ID: {ev_id}]** {title} — {summary}")
            parts.append("")

        return "\n".join(parts)

    def _extract_task_context(self, external_prompt: str) -> str:
        """
        Extract task context from external prompt template.

        This extracts the instructions section to supplement the user prompt
        while keeping the system prompt as the primary instruction source.
        """
        # Look for Instructions section
        if "# Instructions" in external_prompt:
            start = external_prompt.find("# Instructions")
            # Find next section or end
            next_section = external_prompt.find("\n# ", start + 1)
            if next_section > start:
                return external_prompt[start:next_section].strip()
            return external_prompt[start:].strip()

        return ""

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate required input fields."""
        super()._validate_input(input_data)

        if not input_data.get('competitor_name'):
            raise ValueError("competitor_name is required")


def generate_markdown_report(
    competitor_name: str,
    output: FunctionalAuditOutput
) -> str:
    """
    Generate a markdown report from the agent output.

    Handles both JTBD (job_assessments) and legacy (gaps_deep_dive) formats.

    Args:
        competitor_name: Name of the competitor
        output: Validated FunctionalAuditOutput

    Returns:
        Formatted markdown string
    """
    lines = [
        f"# Functional Audit: {competitor_name}",
        "",
        "## 0. Competitor Context",
        "",
        f"**Positioning:** {output.competitor_context.positioning}",
        "",
        f"**Core Differentiation:** {output.competitor_context.core_differentiation}",
        "",
        f"**Target Customer:** {output.competitor_context.target_customer}",
        "",
    ]

    if output.competitor_context.key_features:
        lines.append("**Key Features:**")
        for feature in output.competitor_context.key_features:
            lines.append(f"- {feature}")
        lines.append("")

    # Functional comparison table (with optional job_id column)
    has_job_assessments = hasattr(output, 'job_assessments') and output.job_assessments

    if has_job_assessments:
        lines.extend([
            "## 1. Functional Comparison Table",
            "",
            "| Feature Category | Competitor Feature | Description | Status | Job ID |",
            "|-----------------|-------------------|-------------|--------|--------|",
        ])
        for comp in output.functional_comparison:
            job_id = getattr(comp, 'job_id', None) or ''
            lines.append(
                f"| {comp.feature_category} | {comp.competitor_feature_name} | "
                f"{comp.functional_description} | **{comp.mapping_status}** | {job_id} |"
            )
    else:
        lines.extend([
            "## 1. Functional Comparison Table",
            "",
            "| Feature Category | Competitor Feature | Description | Status |",
            "|-----------------|-------------------|-------------|--------|",
        ])
        for comp in output.functional_comparison:
            lines.append(
                f"| {comp.feature_category} | {comp.competitor_feature_name} | "
                f"{comp.functional_description} | **{comp.mapping_status}** |"
            )

    lines.append("")

    # Section 2: Job assessments or gaps deep dive
    if has_job_assessments:
        lines.extend(["## 2. Job Assessments", ""])
        for ja in output.job_assessments:
            importance_label = f" _(importance: {ja.importance})_" if hasattr(ja, 'importance') and ja.importance else ""
            lines.extend([
                f"### {ja.job_id}: {ja.job_statement}{importance_label}",
                "",
                f"**Our Score:** {ja.our_score}/10 | **Competitor Score:** {ja.competitor_score}/10",
                "",
                f"**Rationale:** {ja.score_rationale}",
                "",
            ])
            # Features that drive the scores (unified advantage + gap view)
            if hasattr(ja, 'features') and ja.features:
                lines.append("**Features driving the scores:**")
                lines.append("")
                lines.append("| Feature | Whose | Position | Description |")
                lines.append("|---------|-------|----------|-------------|")
                cited_evidence = set()
                for feat in ja.features:
                    lines.append(
                        f"| {feat.feature_name} | {feat.whose} | **{feat.position}** | "
                        f"{feat.description} |"
                    )
                    if getattr(feat, 'evidence_ids', None):
                        cited_evidence.update(feat.evidence_ids)
                lines.append("")
                if cited_evidence:
                    lines.append(
                        f"_Evidence cited: {', '.join(str(e) for e in sorted(cited_evidence))}_"
                    )
                    lines.append("")
            # Outcome coverage
            if hasattr(ja, 'outcome_coverage') and ja.outcome_coverage:
                lines.append("**Outcome Coverage:**")
                lines.append("")
                lines.append("| Desired Outcome | Our Coverage | Competitor Coverage |")
                lines.append("|-----------------|--------------|---------------------|")
                for oc in ja.outcome_coverage:
                    lines.append(
                        f"| {oc.desired_outcome} | {oc.our_coverage} | {oc.competitor_coverage} |"
                    )
                lines.append("")
    else:
        lines.extend(["## 2. Deep-Dive on Gaps", ""])
        if output.gaps_deep_dive:
            for gap in output.gaps_deep_dive:
                lines.extend([
                    f"### {gap.feature_name}",
                    "",
                    f"**User Problem:** {gap.user_problem}",
                    "",
                    f"**Evidence:** {gap.evidence}",
                    "",
                ])
        else:
            lines.append("*No significant gaps identified.*")
            lines.append("")

    lines.extend(["## 3. Technical Constraints", ""])

    tc = output.technical_constraints
    if tc.integrations:
        lines.append(f"**Integrations:** {', '.join(tc.integrations)}")
        lines.append("")

    if tc.api_capabilities:
        lines.append(f"**API Capabilities:** {tc.api_capabilities}")
        lines.append("")

    if tc.platform_requirements:
        lines.append(f"**Platform Requirements:** {tc.platform_requirements}")
        lines.append("")

    if tc.additional_notes:
        lines.append(f"**Additional Notes:** {tc.additional_notes}")
        lines.append("")

    return "\n".join(lines)
