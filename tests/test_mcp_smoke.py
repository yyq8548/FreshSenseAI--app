import asyncio

from scripts.smoke_mcp_integration import run_smoke


def test_mcp_use_client_discovers_and_calls_freshsense_tool():
    result = asyncio.run(run_smoke())

    assert result["tool_names"] == ["get_recent_inspections"]
    assert result["structured_content"]["count"] == 1
    assert (
        result["structured_content"]["inspections"][0]["inspection_id"]
        == "smoke-1"
    )
    assert "operator_note" not in result["structured_content"]["inspections"][0]
