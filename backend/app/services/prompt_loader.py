"""
Prompt Loader Service for dynamic prompt template management.

This service loads prompt templates from external markdown files,
enabling runtime modification of prompts without code changes.

Features:
- Caching with configurable TTL for production performance
- Variable substitution with {{variable_name}} syntax
- Graceful error handling for missing files
"""

import os
import time
import re
from typing import Dict, Optional, Tuple
from pathlib import Path


class PromptLoaderService:
    """
    Loads and caches prompt templates from external files.

    Usage:
        loader = PromptLoaderService()
        template = loader.load_prompt("Competitor_Functional_Audit_Prompt.md")
        prompt = loader.substitute_variables(template, {
            "competitor_name": "Acme Corp",
            "product_context": "..."
        })
    """

    def __init__(
        self,
        base_path: str = None,
        cache_ttl: int = 300  # 5 minutes default
    ):
        """
        Initialize the prompt loader.

        Args:
            base_path: Base directory for prompt files. Defaults to docs/development/
            cache_ttl: Cache time-to-live in seconds (0 to disable caching)
        """
        if base_path is None:
            # Default to docs/development relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            base_path = project_root / "docs" / "development"
        self.base_path = Path(base_path)
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[str, float]] = {}  # {filename: (content, timestamp)}

    def load_prompt(self, filename: str, use_cache: bool = True) -> str:
        """
        Load a prompt template from file.

        Args:
            filename: Name of the prompt file (e.g., "Competitor_Functional_Audit_Prompt.md")
            use_cache: Whether to use cached content if available

        Returns:
            The prompt template content as a string

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
            IOError: If there's an error reading the file
        """
        # Check cache first
        if use_cache and self.cache_ttl > 0 and filename in self._cache:
            content, cached_at = self._cache[filename]
            if time.time() - cached_at < self.cache_ttl:
                return content

        # Load from file
        file_path = self.base_path / filename
        if not file_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {file_path}. "
                f"Expected in base_path: {self.base_path}"
            )

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise IOError(f"Error reading prompt file {file_path}: {e}")

        # Update cache
        if self.cache_ttl > 0:
            self._cache[filename] = (content, time.time())

        return content

    def substitute_variables(
        self,
        template: str,
        variables: Dict[str, str],
        strict: bool = False
    ) -> str:
        """
        Replace {{variable_name}} placeholders in template.

        Args:
            template: The prompt template with {{variable}} placeholders
            variables: Dictionary mapping variable names to values
            strict: If True, raise error for missing variables. If False, leave unmatched.

        Returns:
            The template with variables substituted

        Raises:
            ValueError: If strict=True and a required variable is missing
        """
        result = template

        # Replace each variable
        for var_name, value in variables.items():
            # Handle both {{var}} and {{ var }} syntax
            patterns = [
                f"{{{{{var_name}}}}}",
                f"{{{{ {var_name} }}}}",
                f"{{{{{var_name} }}}}",
                f"{{{{ {var_name}}}}}",
            ]
            for pattern in patterns:
                result = result.replace(pattern, str(value))

        # Check for unsubstituted variables if strict mode
        if strict:
            remaining = re.findall(r'\{\{\s*(\w+)\s*\}\}', result)
            if remaining:
                raise ValueError(
                    f"Missing variables in template: {', '.join(set(remaining))}. "
                    f"Provided variables: {', '.join(variables.keys())}"
                )

        return result

    def load_and_substitute(
        self,
        filename: str,
        variables: Dict[str, str],
        strict: bool = False,
        use_cache: bool = True
    ) -> str:
        """
        Convenience method to load a prompt and substitute variables in one call.

        Args:
            filename: Name of the prompt file
            variables: Dictionary mapping variable names to values
            strict: If True, raise error for missing variables
            use_cache: Whether to use cached template

        Returns:
            The fully substituted prompt
        """
        template = self.load_prompt(filename, use_cache=use_cache)
        return self.substitute_variables(template, variables, strict=strict)

    def clear_cache(self, filename: Optional[str] = None):
        """
        Clear cached prompt(s).

        Args:
            filename: Specific file to clear, or None to clear all
        """
        if filename is not None:
            self._cache.pop(filename, None)
        else:
            self._cache.clear()

    def get_available_prompts(self) -> list:
        """
        List all available prompt files in the base directory.

        Returns:
            List of prompt filenames
        """
        if not self.base_path.exists():
            return []

        return [
            f.name for f in self.base_path.iterdir()
            if f.is_file() and f.suffix == '.md'
        ]

    def validate_template_variables(
        self,
        template: str
    ) -> list:
        """
        Extract all variable names from a template.

        Args:
            template: The prompt template to analyze

        Returns:
            List of variable names found in template
        """
        return list(set(re.findall(r'\{\{\s*(\w+)\s*\}\}', template)))


# Global singleton instance
_prompt_loader: Optional[PromptLoaderService] = None


def get_prompt_loader(
    base_path: str = None,
    cache_ttl: int = 300
) -> PromptLoaderService:
    """
    Get or create the global PromptLoaderService instance.

    Args:
        base_path: Base directory for prompt files (only used on first call)
        cache_ttl: Cache TTL in seconds (only used on first call)

    Returns:
        PromptLoaderService instance
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoaderService(base_path=base_path, cache_ttl=cache_ttl)
    return _prompt_loader
