from pathlib import Path


def test_mcp_guide_documents_reproducible_read_only_usage():
    text = Path("docs/MCP_INTEGRATION.md").read_text(encoding="utf-8")
    required = (
        "mcp-use==1.7.0",
        "get_recent_inspections",
        "FRESHSENSE_MCP_API_URL",
        "FRESHSENSE_MCP_API_KEY",
        "FRESHSENSE_MCP_BEARER_TOKEN",
        "MCP_USE_ANONYMIZED_TELEMETRY",
        "--transport stdio",
        "--transport streamable-http",
        "/inspector",
        "does not replace API authorization",
    )
    assert all(value in text for value in required)


def test_readme_links_the_optional_mcp_guide():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "[read-only MCP integration](docs/MCP_INTEGRATION.md)" in text
