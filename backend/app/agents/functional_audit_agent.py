"""
Competitor Functional Audit Agent.

This agent performs a detailed functional audit of a single competitor,
comparing their features against our product to identify gaps and opportunities.

The agent uses an external prompt template (Competitor_Functional_Audit_Prompt.md)
for flexibility in production environments.
"""

from typing import Dict, Any, Type

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.schemas.competitive_reports import FunctionalAuditOutput
from app.services.prompt_loader import get_prompt_loader
from app.services.html_cleaner import get_html_cleaner


class CompetitorFunctionalAuditAgent(BaseAgent):
    """
    Per-competitor functional audit agent.

    Analyzes a single competitor to produce:
    - Competitor context (positioning, differentiation, target customer)
    - Functional comparison table (Parity/Advantage/Gap/Differentiator)
    - Deep-dive on gaps
    - Technical constraints

    Usage:
        agent = CompetitorFunctionalAuditAgent(db=db, llm_service=llm_service)
        result = agent.execute({
            'competitor_name': 'Acme Corp',
            'competitor_url': 'https://acme.com',
            'product_context': {...},  # Our product info
            'web_search_results': [...]  # Search results about competitor
        })
    """

    PROMPT_FILENAME = "Competitor_Functional_Audit_Prompt.md"

    def get_stage(self) -> str:
        """Return the pipeline stage for this agent."""
        return "functional_audit"

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the Pydantic schema for output validation."""
        return FunctionalAuditOutput

    def get_system_prompt(self) -> str:
        """
        Build system prompt with JSON output instructions.

        The role and task context come from the external prompt template.
        We append JSON formatting instructions here.
        """
        return """You are a Technical Product Analyst specializing in B2B SaaS functional decomposition.

Your task is to conduct a rigorous competitive and functional audit of a competitor product.
Move past marketing language and identify specific "how-it-works" capabilities.

## Output Format

You MUST respond with a valid JSON object matching this exact structure:

```json
{
  "competitor_context": {
    "positioning": "Their hero message and self-description",
    "core_differentiation": "What makes them unique",
    "target_customer": "Their ideal customer profile",
    "key_features": ["Feature 1", "Feature 2", "Feature 3", "Feature 4", "Feature 5"]
  },
  "functional_comparison": [
    {
      "feature_category": "Category name",
      "competitor_feature_name": "Feature name",
      "functional_description": "What it actually does",
      "mapping_status": "Gap"
    }
  ],
  "gaps_deep_dive": [
    {
      "feature_name": "Feature name",
      "user_problem": "Pain point this solves",
      "evidence": "Quote or description proving value"
    }
  ],
  "technical_constraints": {
    "integrations": ["Integration 1", "Integration 2"],
    "api_capabilities": "API description or null",
    "platform_requirements": "Platform requirements or null",
    "additional_notes": "Other notes or null"
  }
}
```

## Mapping Status Definitions

- **Parity**: Functionality exists in both products with similar depth
- **Advantage**: We have this feature; they do not
- **Gap**: They have this feature; we do not
- **Differentiator**: A unique feature they offer that significantly alters user workflow

## Important Guidelines

1. Identify 8-15 key features (prioritize quality over quantity)
2. Be specific but concise - describe functional capabilities in 1-2 sentences
3. Focus on Gaps and Differentiators - these are most valuable
4. Keep descriptions brief - avoid lengthy explanations
5. Output ONLY valid JSON - no markdown code blocks, no explanatory text
6. Ensure all strings are properly escaped and the JSON is complete"""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        Build the user prompt with competitor data.

        Args:
            input_data: Must contain:
                - competitor_name: Name of competitor
                - competitor_url: URL of competitor
                - product_context: Dict with our product info
                - web_search_results: List of search result dicts OR pre-formatted string
        """
        competitor_name = input_data.get('competitor_name', 'Unknown Competitor')
        competitor_url = input_data.get('competitor_url', '')
        product_context = input_data.get('product_context', {})
        web_search_results = input_data.get('web_search_results', [])

        # Format product context
        product_info = self._format_product_context(product_context)

        # Format search results (clean HTML if needed)
        search_content = self._format_search_results(web_search_results)

        # Try to load external prompt template for additional context
        prompt_loader = get_prompt_loader()
        try:
            external_prompt = prompt_loader.load_prompt(self.PROMPT_FILENAME)
            # Extract just the task/instructions sections from external prompt
            task_context = self._extract_task_context(external_prompt)
        except FileNotFoundError:
            task_context = ""

        prompt = f"""# Competitor Analysis Request

## Competitor Information
- **Name:** {competitor_name}
- **URL:** {competitor_url}

## Our Product Context
{product_info}

## Competitor Source Data
{search_content}

{task_context}

## Your Task

Analyze {competitor_name} and produce a comprehensive functional audit report.
Focus on identifying their actual capabilities, not marketing claims.
For each feature gap identified, provide evidence of its value.

Respond with ONLY a valid JSON object following the schema in the system prompt."""

        return prompt

    def _format_product_context(self, product_context: Dict[str, Any]) -> str:
        """Format our product context for the prompt."""
        if not product_context:
            return "No product context provided."

        parts = []

        if product_context.get('product_name'):
            parts.append(f"**Product Name:** {product_context['product_name']}")

        if product_context.get('product_category'):
            parts.append(f"**Category:** {product_context['product_category']}")

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

    lines.extend(["", "## 2. Deep-Dive on Gaps", ""])

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
