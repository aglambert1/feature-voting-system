"""
Feature Extractor Agent

Extracts features from competitor websites with support for:
- Fresh extraction (first-time analysis)
- Comparative analysis (detects changes from previous sessions)
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field, HttpUrl
from app.agents.base_agent import BaseAgent


# ============================================================================
# Output Schemas
# ============================================================================

class ExtractedFeature(BaseModel):
    """Single extracted feature (fresh mode)"""
    name: str = Field(..., max_length=255, description="Feature name (2-5 words)")
    description: str = Field(..., description="Feature description (1-2 sentences)")
    category: str = Field(..., description="Feature category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source_url: str = Field(..., description="URL where feature was found")
    raw_context: Optional[str] = Field(None, description="Raw text context")


class FeatureExtractionOutput(BaseModel):
    """Output schema for fresh feature extraction"""
    competitor_name: str
    features: List[ExtractedFeature] = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Extracted features (extract 10-25 when possible, minimum 3)"
    )
    extraction_summary: str = Field(
        ...,
        description="Brief summary of extraction process"
    )


class FeatureWithComparison(BaseModel):
    """Feature with change detection (comparative mode)"""
    name: str
    description: str
    category: str
    confidence: float
    source_url: str
    raw_context: Optional[str] = None
    change_type: str = Field(..., pattern="^(new|modified|unchanged|removed)$")
    change_description: Optional[str] = Field(None, description="What changed")
    previous_feature_id: Optional[str] = None


class ComparativeFeatureOutput(BaseModel):
    """Output schema for comparative feature extraction"""
    competitor_name: str
    analysis_mode: str = Field(..., pattern="^(fresh|comparative)$")
    features: List[FeatureWithComparison]
    summary: Dict[str, int] = Field(
        ...,
        description="Feature counts by change type"
    )


# ============================================================================
# Feature Extractor Agent
# ============================================================================

class FeatureExtractorAgent(BaseAgent):
    """
    Extracts product features from competitor websites.

    Can operate in two modes:
    1. Fresh extraction (no previous data)
    2. Comparative analysis (detects changes from previous analysis)
    """

    def get_system_prompt(self) -> str:
        return """You are a Feature Extraction agent specializing in competitive intelligence.

Your role is to thoroughly research a competitor's product and extract their features.
Extract features that you can confidently identify - don't guess or extrapolate.

**MULTI-URL RESEARCH STRATEGY:**
Use a systematic approach to research multiple pages of the competitor website:
1. **Homepage** - Understand core product positioning and main features
2. **Features/Product Page** - Detailed feature descriptions and capabilities
3. **Pricing Page** - Pricing tiers, editions, and feature differences
4. **Documentation/Help Center** - Technical specifications and detailed info
5. **Blog/Release Notes** - Recent features, updates, and improvements

For each feature, record the specific source URL where you found it (not just homepage).

You can operate in two modes:

**FRESH EXTRACTION MODE:**
- Research multiple pages systematically to extract distinct features
- Target 10-25 features if available, but extract minimum 3 verified features
- Focus on tangible, verifiable features found across product pages
- Categorize features logically
- Assign confidence scores based on information clarity and certainty
- Always specify the exact source_url where you found each feature
- It's okay to extract fewer features if you can't verify more

**COMPARATIVE ANALYSIS MODE:**
- Extract current features using multi-page research as above
- Compare with previous features to identify changes
- Categorize each feature as: NEW, MODIFIED, UNCHANGED, or REMOVED
- Explain what changed for modified features
- Be precise about actual changes vs. minor wording differences

Always respond with valid JSON matching the specified schema.
Focus on facts, verifiable capabilities across multiple sources.
Never hallucinate features to reach a target count."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        competitor_name = input_data.get('competitor_name', '')
        competitor_url = input_data.get('competitor_url', '')
        previous_features = input_data.get('previous_features', None)

        if previous_features:
            # Comparative mode
            prompt = f"""COMPARATIVE ANALYSIS MODE

Research the competitor and compare with previous analysis:

**Competitor:** {competitor_name}
**Website:** {competitor_url}

**Previous Features (from last analysis):**
{self._format_previous_features(previous_features)}

**MULTI-PAGE RESEARCH STRATEGY:**
Systematically research multiple pages to track changes:
1. Homepage - Check positioning changes
2. Features/Product page - Compare detailed feature lists
3. Pricing page - Check for tier/feature changes
4. Documentation - Look for new technical capabilities
5. Blog/Release notes - Identify recently added features

**Your Tasks:**
1. Systematically research {competitor_url} across multiple pages for current features
2. For each feature, compare with previous features to determine:
   - **NEW**: Feature not present in previous analysis
   - **MODIFIED**: Feature changed (description, category, capability, or availability)
   - **UNCHANGED**: Feature remains the same
   - **REMOVED**: Previous feature no longer found or documented

3. For each current feature, provide:
   - name: Concise feature name (2-5 words)
   - description: Clear description (1-2 sentences)
   - category: Logical category (e.g., "Core Functionality", "Integration", "Analytics")
   - confidence: 0.0-1.0 based on information clarity
   - source_url: Specific page where found (e.g., /features, /pricing, /docs - NOT just homepage)
   - change_type: "new", "modified", "unchanged", or "removed"
   - change_description: Brief explanation of what changed (for modified features)
   - previous_feature_id: ID of matching previous feature (if applicable)

4. Provide summary counts:
   - total_features: Total current features found
   - new_features: Features newly added
   - modified_features: Features that changed
   - unchanged_features: Features that stayed the same
   - removed_features: Previous features no longer present

IMPORTANT:
- Research multiple pages, not just the homepage
- Always record specific source_url where each feature is found
- Be precise about actual changes vs. minor wording differences

Return the results EXACTLY in this JSON format:
{{
  "competitor_name": "{competitor_name}",
  "analysis_mode": "comparative",
  "features": [
    {{
      "name": "Feature Name",
      "description": "Feature description",
      "category": "Category",
      "confidence": 0.9,
      "source_url": "{competitor_url}",
      "raw_context": "Optional context",
      "change_type": "new",
      "change_description": "This is a new feature",
      "previous_feature_id": null
    }}
  ],
  "summary": {{
    "total_features": 15,
    "new_features": 5,
    "modified_features": 3,
    "unchanged_features": 7,
    "removed_features": 0
  }}
}}

Guidelines:
- Be precise about actual changes vs. cosmetic differences
- "Modified" means substantive capability change, not just rewording
- Include removed features in the output with change_type="removed"
"""
        else:
            # Fresh extraction mode
            prompt = f"""FRESH EXTRACTION MODE

Research and extract features from:

**Competitor:** {competitor_name}
**Website:** {competitor_url}

**MULTI-PAGE RESEARCH STRATEGY:**
Systematically research multiple pages to get a complete picture:
1. Homepage - Understand the product's core positioning
2. Features/Product page - Detailed feature descriptions
3. Pricing page - Different tiers and their feature sets
4. Documentation/Help center - Technical capabilities
5. Blog/Release notes - Recent features and improvements

**Your Tasks:**
1. Systematically research {competitor_url} across multiple pages
2. Extract distinct features or capabilities you can verify (target 10-25 if available, minimum 3)
3. For each feature, provide:
   - name: Concise feature name (2-5 words)
   - description: Clear description (1-2 sentences)
   - category: Logical category (e.g., "Core Functionality", "Integration", "Analytics", "Pricing Model")
   - confidence: 0.0-1.0 based on how clearly documented the feature is
   - source_url: Specific page where you found this feature (e.g., /features, /pricing, /docs - NOT just homepage)
   - raw_context: Optional snippet of relevant text

4. Also provide extraction_summary: Brief summary of what you found

IMPORTANT:
- Only extract features you can verify across the product pages
- Don't guess or make up features to reach a target number
- Always record the specific source_url where you found each feature
- Research multiple pages, not just the homepage

Return the results EXACTLY in this JSON format:
{{
  "competitor_name": "{competitor_name}",
  "features": [
    {{
      "name": "Feature Name",
      "description": "Feature description (1-2 sentences)",
      "category": "Core Functionality",
      "confidence": 0.9,
      "source_url": "{competitor_url}",
      "raw_context": "Optional relevant text snippet"
    }}
  ],
  "extraction_summary": "Brief summary of extraction process"
}}

Guidelines:
- Focus on tangible, verifiable features
- Avoid vague marketing terms
- Categorize logically
- Be specific and factual
"""

        return prompt

    def _format_previous_features(self, features: List[Dict]) -> str:
        """Format previous features for prompt"""
        if not features:
            return "(No previous features)"

        lines = []
        for i, feat in enumerate(features, 1):
            feat_id = feat.get('id', 'unknown')
            name = feat.get('name', 'Unknown')
            desc = feat.get('description', 'N/A')
            category = feat.get('category', 'N/A')
            lines.append(f"{i}. [{feat_id}] {name} ({category}): {desc}")
        return '\n'.join(lines)

    def get_output_schema(self) -> Type[BaseModel]:
        # Return appropriate schema based on mode
        # Will be set dynamically in execute()
        return getattr(self, '_output_schema', FeatureExtractionOutput)

    def get_stage(self) -> str:
        return "feature_extraction"

    def execute(
        self,
        input_data: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Override execute to handle dynamic schema selection.
        """
        # Determine mode and set appropriate schema
        has_previous = input_data.get('previous_features') is not None

        if has_previous:
            self._output_schema = ComparativeFeatureOutput
        else:
            self._output_schema = FeatureExtractionOutput

        return super().execute(input_data, temperature, max_tokens, max_retries)


# ============================================================================
# Feature Detail Expander Agent
# ============================================================================

class ExpandedFeatureDetail(BaseModel):
    """Output schema for expanded feature details"""
    expanded_description: str
    technical_details: str
    use_cases: List[str]
    benefits: List[str]
    limitations: Optional[List[str]] = None
    related_features: Optional[List[str]] = None


class FeatureDetailExpanderAgent(BaseAgent):
    """
    Expands details for a specific feature on user request.
    """

    def get_system_prompt(self) -> str:
        return """You are a Feature Detail Expander agent.

Your role is to provide expanded, detailed information about a specific product feature.

Include:
- Technical details and specifications
- Use cases and practical applications
- Benefits and value proposition
- Any limitations or requirements
- Related features or integrations

Be thorough but clear. Focus on helping users understand the feature deeply.

Always respond with valid JSON matching the specified schema."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        feature_name = input_data.get('feature_name', '')
        feature_description = input_data.get('feature_description', '')
        competitor_name = input_data.get('competitor_name', '')
        competitor_url = input_data.get('competitor_url', '')

        prompt = f"""Provide detailed information about this feature:

**Feature:** {feature_name}
**Current Description:** {feature_description}
**Competitor:** {competitor_name}
**Source:** {competitor_url}

Expand on this feature with:
1. **Technical Details**: How it works, specifications, capabilities
2. **Use Cases**: Practical scenarios where this feature is valuable
3. **Benefits**: Value it provides to users
4. **Limitations**: Any constraints or requirements
5. **Related Features**: Other features that work with this

Return the results EXACTLY in this JSON format:
{{
  "expanded_description": "Detailed multi-paragraph description",
  "technical_details": "Technical information about how it works",
  "use_cases": ["Use case 1", "Use case 2", "Use case 3"],
  "benefits": ["Benefit 1", "Benefit 2", "Benefit 3"],
  "limitations": ["Limitation 1", "Limitation 2"] or null,
  "related_features": ["Feature 1", "Feature 2"] or null
}}

Be specific and provide actionable information."""
        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        return ExpandedFeatureDetail

    def get_stage(self) -> str:
        return "feature_detail_expansion"
