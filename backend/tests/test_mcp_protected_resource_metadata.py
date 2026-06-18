"""Tests for the RFC 9728 OAuth Protected Resource Metadata endpoint.

The claude.ai custom-connector OAuth flow requires this document at
/.well-known/oauth-protected-resource to discover which authorization server
protects /mcp. Its absence breaks connector OAuth while the config-file/
mcp-remote path keeps working (that path skips discovery).
"""

from unittest.mock import patch


class TestProtectedResourceMetadata:
    def test_authorization_servers_matches_issuer_trailing_slash(self):
        """authorization_servers MUST match the issuer advertised by
        oauth-authorization-server exactly — including the trailing slash the
        SDK adds — or claude.ai silently falls back to manual config."""
        with patch("mcp_server.http_server.settings") as s:
            s.mcp_base_url = "https://feature-iq-mcp.onrender.com"
            import mcp_server.http_server as h
            meta = h._protected_resource_metadata()
        assert meta["authorization_servers"] == ["https://feature-iq-mcp.onrender.com/"]

    def test_resource_has_no_trailing_slash(self):
        with patch("mcp_server.http_server.settings") as s:
            s.mcp_base_url = "https://feature-iq-mcp.onrender.com"
            import mcp_server.http_server as h
            meta = h._protected_resource_metadata()
        assert meta["resource"] == "https://feature-iq-mcp.onrender.com/mcp"

    def test_issuer_form_stable_regardless_of_env_trailing_slash(self):
        """A trailing slash on the configured base_url must not produce a
        double slash in resource or a mismatched issuer."""
        with patch("mcp_server.http_server.settings") as s:
            s.mcp_base_url = "https://feature-iq-mcp.onrender.com/"
            import mcp_server.http_server as h
            meta = h._protected_resource_metadata()
        assert meta["resource"] == "https://feature-iq-mcp.onrender.com/mcp"
        assert meta["authorization_servers"] == ["https://feature-iq-mcp.onrender.com/"]

    def test_required_rfc9728_fields_present(self):
        with patch("mcp_server.http_server.settings") as s:
            s.mcp_base_url = "https://feature-iq-mcp.onrender.com"
            import mcp_server.http_server as h
            meta = h._protected_resource_metadata()
        assert meta["scopes_supported"] == ["mcp"]
        assert meta["bearer_methods_supported"] == ["header"]

    def test_both_well_known_paths_registered(self):
        """Spec places the doc at the resource-suffixed path; clients also probe
        the bare path. Both must be registered against the handler."""
        import mcp_server.http_server as h
        paths = {
            r.path
            for r in h.mcp._additional_http_routes
            if "oauth-protected-resource" in getattr(r, "path", "")
        }
        assert "/.well-known/oauth-protected-resource" in paths
        assert "/.well-known/oauth-protected-resource/mcp" in paths
