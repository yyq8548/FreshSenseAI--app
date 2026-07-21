import asyncio

from freshsense_mcp.server import create_server


class FakeApiClient:
    def __init__(self):
        self.calls = []

    def get_recent_inspections(self, *, limit=10, review_status=None):
        self.calls.append((limit, review_status))
        return {
            "count": 1,
            "inspections": [{"inspection_id": "inspection-1"}],
        }


def test_server_exposes_one_typed_read_only_tool():
    server = create_server(api_client=FakeApiClient())
    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == ["get_recent_inspections"]
    tool = tools[0]
    assert "recent FreshSense inspection" in tool.description
    assert tool.inputSchema["properties"]["limit"]["minimum"] == 1
    assert tool.inputSchema["properties"]["limit"]["maximum"] == 50
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is True


def test_tool_delegates_to_the_minimized_api_client():
    api_client = FakeApiClient()
    server = create_server(api_client=api_client)

    _, structured_result = asyncio.run(
        server.call_tool(
            "get_recent_inspections",
            {"limit": 4, "review_status": "pending"},
        )
    )

    assert api_client.calls == [(4, "pending")]
    assert structured_result["count"] == 1
    assert structured_result["inspections"][0]["inspection_id"] == "inspection-1"
