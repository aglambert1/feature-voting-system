"""
Product Analyzer Agent for competitive intelligence.

This agent analyzes product descriptions and extracts structured information
for competitive analysis, including features, target users, and search keywords.
"""

from typing import Dict, Any, Type
from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent


class ProductAnalysisOutput(BaseModel):
    """Output schema for Product Analyzer Agent."""
    product_name: str = Field(..., description="Extracted or confirmed product name")
    product_category: str = Field(..., description="Product category/industry")
    core_features: list[str] = Field(
        ...,
        description="5-7 core features or capabilities",
        min_length=3,
        max_length=10
    )
    target_users: str = Field(..., description="Target users/customers description")
    value_propositions: list[str] = Field(
        ...,
        description="Unique value propositions",
        min_length=1,
        max_length=5
    )
    competitor_search_keywords: list[str] = Field(
        ...,
        description="Keywords for finding competitors",
        min_length=3,
        max_length=10
    )


class ProductAnalyzerAgent(BaseAgent):
    """
    Analyzes product descriptions and structures them for competitive analysis.

    Handles input from:
    - Text descriptions
    - Uploaded documents (extracted text)
    - URLs (webpage content)

    Example:
        agent = ProductAnalyzerAgent(db=db, llm_service=llm_service)
        result = agent.execute({
            'product_name': 'My CRM',
            'product_description': 'A CRM for small businesses...',
            'source_type': 'text'
        })
    """

    def get_system_prompt(self) -> str:
        """Define the agent's system prompt."""
        return """You are a Product Analyzer agent specializing in competitive intelligence.

Your role is to analyze product descriptions and extract structured information that will be used to:
1. Find competing products
2. Compare features across competitors
3. Generate strategic insights

You must be thorough but concise. Focus on aspects relevant to competitive analysis.

Always respond with valid JSON matching the specified schema.
Do not include any markdown formatting or code blocks - just the raw JSON."""

    def build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """Build the user prompt from input data."""
        product_name = input_data.get('product_name', '')
        product_description = input_data.get('product_description', '')
        source_type = input_data.get('source_type', 'text')

        prompt = f"""Analyze the following product information and extract structured data:

Product Name: {product_name if product_name else "(extract from description)"}
Source Type: {source_type}
Product Description:
{product_description}

Extract and return the following information in JSON format:

1. **product_name**: The product name (use provided name or extract from description)
2. **product_category**: The industry/category (e.g., "CRM Software", "Project Management", "E-commerce Platform")
3. **core_features**: List 5-7 key features or capabilities that define this product
4. **target_users**: Describe who uses this product (roles, company sizes, industries)
5. **value_propositions**: List 2-4 unique value propositions or competitive advantages
6. **competitor_search_keywords**: List 5-10 keywords/phrases to use when searching for competing products

Guidelines:
- Be specific and concrete
- Focus on differentiating characteristics
- Use industry-standard terminology
- Keywords should be search-friendly (2-4 words each)
- Avoid marketing fluff, focus on substance

Return ONLY the JSON object, no additional text.

Example format:
{{"product_name": "Example CRM", "product_category": "CRM Software", "core_features": ["Contact management", "Sales pipeline", "Email integration", "Reporting dashboard", "Mobile app"], "target_users": "Small to medium-sized B2B companies with 10-100 employees", "value_propositions": ["Easy setup in under 5 minutes", "Affordable pricing for startups"], "competitor_search_keywords": ["crm software", "contact management", "sales pipeline tool", "customer relationship management", "small business crm"]}}
"""
        return prompt

    def get_output_schema(self) -> Type[BaseModel]:
        """Return the output schema."""
        return ProductAnalysisOutput

    def get_stage(self) -> str:
        """Return the stage name."""
        return "product_analysis"
