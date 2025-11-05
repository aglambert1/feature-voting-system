"""
LLM Service for Claude API integration.

This service handles all interactions with the Anthropic Claude API,
including structuring freeform text into what/why/use_case format.
"""

import time
import json
from typing import Dict
from anthropic import Anthropic, APIError, APITimeoutError

from app.config import settings


class LLMService:
    """
    Service for interacting with Claude API.

    Handles text structuring and error handling.
    """

    def __init__(self):
        """Initialize the Anthropic client."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        # Use Claude 3 Haiku (fast and cost-effective for structuring tasks)
        self.model = "claude-3-haiku-20240307"

    def structure_idea(self, freeform_text: str) -> Dict[str, any]:
        """
        Structure freeform text into a structured idea format.

        Takes natural language input and returns structured data with:
        - title: Short, descriptive title
        - what_description: What the feature is
        - why_description: Why it's valuable
        - use_case_description: How it would be used

        Args:
            freeform_text: User's freeform idea description

        Returns:
            Dictionary with structured idea and processing time

        Raises:
            APIError: If Claude API returns an error
            APITimeoutError: If request times out
            ValueError: If response cannot be parsed
        """
        start_time = time.time()

        # Construct the prompt for Claude
        prompt = f"""You are a product manager helping structure feature ideas.

A user has submitted the following idea in their own words:

<user_idea>
{freeform_text}
</user_idea>

Please structure this idea into a clear, professional format with four components:

1. **Title**: A concise, descriptive title (5-8 words max)
2. **What**: A clear description of what the feature is (2-3 sentences)
3. **Why**: Explanation of why this feature would be valuable (2-3 sentences)
4. **Use Case**: A concrete example of how someone would use this feature (2-3 sentences)

Return ONLY a JSON object with these exact keys: title, what, why, use_case
Do not include any markdown formatting, code blocks, or additional text - just the raw JSON.

Example format:
{{"title": "Dark Mode Toggle", "what": "A toggle switch in settings that...", "why": "This would improve...", "use_case": "A user working late at night..."}}"""

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract the response text
            response_text = message.content[0].text.strip()

            # Parse JSON response
            try:
                structured_data = json.loads(response_text)
            except json.JSONDecodeError:
                # If Claude wrapped response in markdown code blocks, clean it
                if response_text.startswith("```"):
                    # Remove code block markers
                    response_text = response_text.strip("`").strip()
                    if response_text.startswith("json"):
                        response_text = response_text[4:].strip()
                    structured_data = json.loads(response_text)
                else:
                    raise ValueError(f"Could not parse Claude response as JSON: {response_text}")

            # Validate required fields
            required_fields = ["title", "what", "why", "use_case"]
            missing_fields = [field for field in required_fields if field not in structured_data]
            if missing_fields:
                raise ValueError(f"Missing required fields in response: {missing_fields}")

            # Calculate processing time
            processing_time = time.time() - start_time

            # Return structured data with metadata
            return {
                "title": structured_data["title"],
                "what_description": structured_data["what"],
                "why_description": structured_data["why"],
                "use_case_description": structured_data["use_case"],
                "processing_time": round(processing_time, 2)
            }

        except APITimeoutError as e:
            print(f"Claude API timeout: {e}")
            raise Exception("AI processing timed out. Please try again.")

        except APIError as e:
            print(f"Claude API error: {e}")
            raise Exception(f"AI processing failed: {str(e)}")

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Response was: {response_text}")
            raise ValueError("AI returned invalid format. Please try again.")

        except Exception as e:
            print(f"Unexpected error in structure_idea: {e}")
            raise Exception(f"Unexpected error during AI processing: {str(e)}")


# Create a singleton instance for reuse
llm_service = LLMService()
