from app.core.settings import get_guardrails
from app.presentation.api.mcp import mcp


def test_six_scopes_are_guardrail_owned():
    assert set(get_guardrails().get("security.scopes")) == {
        "case:read", "case:write", "order:read", "return:read", "action:approve", "mcp:read"
    }


def test_mcp_has_exactly_three_read_scoped_tools():
    tools = mcp._tool_manager._tools
    assert set(tools) == {"get_my_cases", "get_case_detail", "open_support_case"}
    assert all(tool.meta["required_scope"] == "mcp:read" for tool in tools.values())
