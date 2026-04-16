"""
Job Map Extractor Agent for JTBD competitive analysis.

This agent analyzes product information and extracts a proposed JTBD job map
including target customer profile, functional/emotional/social jobs, and
desired outcomes for each job.
"""

from typing import Any, Dict, Type

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.schemas.job_map import JobMapExtractionOutput


class JobMapExtractorAgent(BaseAgent):
    """
    Extracts a proposed JTBD job map from product information.

    Analyzes the product description, features, value propositions, and any
    available evidence to produce a hierarchical job map grounded in Clayton
    Christensen's Jobs-to-be-Done framework.

    The output is a PROPOSAL — the PO iterates on it using granular
    editing tools (product_edit_job, product_add_job, etc.).
    """

    def get_system_prompt(self) -> str:
        return """You are a Product Strategy Analyst specializing in Clayton Christensen's Jobs-to-be-Done (JTBD) framework.

Your task is to analyze a product and extract:
1. A target customer profile — who is hiring this product and why
2. A hierarchical job map — the jobs customers need done

## JTBD Framework
- Products are "hired" by customers to make progress in specific circumstances
- Jobs have three dimensions:
  - Functional: the practical task ("When I need to [do X], I want to [action], so I can [outcome]")
  - Emotional: how they want to feel ("When [situation], I want to feel [state], so I can [benefit]")
  - Social: how they want to be perceived ("When [context], I want to be perceived as [quality]")
- Each job has desired outcomes — measurable criteria for success
- Jobs are stable over time; solutions change. Focus on the underlying need, not the product feature.

## Instructions
1. Infer the target customer from the product description, features, and category
2. Identify the main job — the overall progress the customer is trying to make
3. Extract 3-8 functional sub-jobs (the core of the map)
4. Extract 1-3 emotional sub-jobs
5. Extract 1-2 social sub-jobs
6. For each sub-job, list 1-3 desired outcomes as plain strings
7. Rate importance: critical (must-have), high (strong need), medium (nice-to-have), low (minor)

## Key principles
- Frame jobs from the CUSTOMER's perspective, not the product's perspective
- Jobs should be solution-agnostic (not "use feature X" but "accomplish task Y")
- Desired outcomes should be measurable where possible ("minimize time to...", "reduce errors in...")
- If PO guidance is provided, prioritize their domain knowledge over inference

## Job ID convention
- Functional: j1, j2, j3...
- Emotional: je1, je2...
- Social: js1, js2..."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        product_name = input_data.get("product_name", "Unknown Product")
        product_description = input_data.get("product_description", "")
        product_category = input_data.get("product_category", "")
        structured_data = input_data.get("structured_product_data") or {}
        evidence_summaries = input_data.get("evidence_summaries") or []
        guidance = input_data.get("guidance")

        # Build features section
        features_section = ""
        features = structured_data.get("detailed_features") or structured_data.get("core_features") or []
        if features:
            if isinstance(features[0], dict):
                feature_lines = [
                    f"- {f.get('name', '')}: {f.get('description', '')}"
                    for f in features
                ]
            else:
                feature_lines = [f"- {f}" for f in features]
            features_section = "\n## Product Features\n" + "\n".join(feature_lines)

        # Build value propositions section
        vp_section = ""
        value_props = structured_data.get("value_propositions") or []
        if value_props:
            vp_lines = [f"- {vp}" for vp in value_props]
            vp_section = "\n## Value Propositions\n" + "\n".join(vp_lines)

        # Build evidence section
        evidence_section = ""
        if evidence_summaries:
            ev_lines = []
            for ev in evidence_summaries:
                ev_lines.append(
                    f"- [{ev.get('type', 'unknown')}] {ev.get('title', '')}: "
                    f"{ev.get('content', '')}"
                )
            evidence_section = "\n## Available Evidence\n" + "\n".join(ev_lines)

        # Build guidance section
        guidance_section = ""
        if guidance:
            guidance_section = (
                f"\n## Product Owner Guidance\n"
                f"The product owner has provided the following context — "
                f"prioritize this domain knowledge:\n{guidance}"
            )

        prompt = f"""Analyze the following product and extract a JTBD job map.

## Product Information
- **Name**: {product_name}
- **Category**: {product_category or '(infer from description)'}
- **Description**: {product_description}
{features_section}
{vp_section}
{evidence_section}
{guidance_section}

## Required Output

Return a JSON object with these fields:

1. **target_customer_profile**: object with:
   - persona_name: Short name for the persona (e.g., "Mid-market Operations Director")
   - company_characteristics: Company size, industry, stage (or null)
   - key_traits: List of key behavioral traits or constraints
   - hiring_criteria: What would make them "hire" this product (or null)

2. **job_map**: object with:
   - main_job: The overarching job statement (one sentence)
   - functional_jobs: List of 3-8 jobs, each with:
     - job_id: "j1", "j2", etc.
     - job_type: "functional"
     - statement: Job statement in JTBD format ("When [situation], I want to [action], so I can [outcome]")
     - desired_outcomes: List of 1-3 outcome strings (measurable where possible)
     - importance: "critical", "high", "medium", or "low"
   - emotional_jobs: List of 1-3 jobs (same structure, job_type: "emotional", IDs: "je1", "je2"...)
   - social_jobs: List of 1-2 jobs (same structure, job_type: "social", IDs: "js1", "js2"...)

3. **extraction_notes**: Optional string noting confidence level or areas needing PO input

IMPORTANT:
- Frame ALL jobs from the customer's perspective, never the product's
- Use solution-agnostic language
- Make desired outcomes measurable where possible"""

        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return JobMapExtractionOutput

    def get_stage(self) -> str:
        return "job_map_extraction"
