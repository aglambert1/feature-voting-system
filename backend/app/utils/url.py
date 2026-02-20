"""
URL normalization utilities for consistent comparison across the application.

Used by competitor deduplication, product loading, and anywhere URLs
need to be compared for equivalence.
"""

from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent comparison.

    Strips scheme, 'www.' prefix, trailing slashes, and lowercases the result.
    Returns the normalized domain + path string.

    Examples:
        normalize_url("https://www.Example.com/") -> "example.com"
        normalize_url("http://Example.com/product") -> "example.com/product"
        normalize_url("example.com") -> "example.com"
        normalize_url("") -> ""
    """
    if not url:
        return ""

    url = url.strip()

    # Ensure there's a scheme so urlparse can extract the netloc
    parse_url = url if "://" in url else f"https://{url}"

    parsed = urlparse(parse_url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    path = parsed.path if parsed.netloc else "/" + "/".join(parsed.path.split("/")[1:])

    # Strip www. prefix and lowercase
    domain = domain.lower().removeprefix("www.")

    # Strip trailing slashes from path, then combine
    path = path.rstrip("/")

    # Only include path if it's non-empty (not just the root)
    if path and path != "/":
        return f"{domain}{path}"
    return domain


def extract_domain(url: str) -> str:
    """
    Extract just the domain from a URL, normalized.

    Examples:
        extract_domain("https://www.example.com/page") -> "example.com"
        extract_domain("http://sub.example.com") -> "sub.example.com"
        extract_domain("") -> ""
    """
    if not url:
        return ""

    url = url.strip()
    parse_url = url if "://" in url else f"https://{url}"

    parsed = urlparse(parse_url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    return domain.lower().removeprefix("www.")
