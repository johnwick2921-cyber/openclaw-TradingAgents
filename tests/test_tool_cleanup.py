"""Verify all tool files are plain Python functions with zero LangChain dependency."""
import sys


def test_no_langchain_in_kept_utils():
    """The kept utils files (agent_utils, agent_states, *_tools) should not import langchain.
    Note: agents/__init__.py still imports from agent .py files that WILL be deleted in Phase 8.
    This test checks only the files we're KEEPING.
    """
    import subprocess
    result = subprocess.run(
        ["grep", "-r", "langchain",
         "openclaw/tools/",
         "--include=*.py"],
        capture_output=True, text=True,
        cwd="/home/hoang/.openclaw"
    )
    assert result.stdout.strip() == "", f"langchain found in utils/: {result.stdout}"


def test_get_stock_data_is_plain_function():
    """get_stock_data should be a plain function, not a LangChain StructuredTool."""
    from openclaw.tools import get_stock_data
    assert type(get_stock_data).__name__ == "function", f"Expected function, got {type(get_stock_data)}"


def test_get_indicators_is_plain_function():
    from openclaw.tools import get_indicators
    assert type(get_indicators).__name__ == "function", f"Expected function, got {type(get_indicators)}"


def test_get_news_is_plain_function():
    from openclaw.tools import get_news
    assert type(get_news).__name__ == "function", f"Expected function, got {type(get_news)}"


def test_get_fundamentals_is_plain_function():
    from openclaw.tools import get_fundamentals
    assert type(get_fundamentals).__name__ == "function", f"Expected function, got {type(get_fundamentals)}"


# ─── Tool Registry Tests ────────────────────────────────────────────────

def test_registry_has_default_tools():
    """All default strategy tools should be auto-registered on import."""
    from openclaw.tool_registry import registry
    import openclaw.tools  # triggers registration

    expected = [
        "get_stock_data", "get_indicators", "get_fundamentals",
        "get_balance_sheet", "get_cashflow", "get_income_statement",
        "get_news", "get_global_news", "get_insider_transactions",
    ]
    for name in expected:
        assert name in registry, f"Tool '{name}' not registered"


def test_registry_call_returns_string():
    """Registered tool should be callable and return a string."""
    from openclaw.tool_registry import ToolRegistry

    reg = ToolRegistry()
    reg.register(
        name="mock_tool",
        fn=lambda x: f"result for {x}",
        param_builder=lambda ctx: {"x": ctx["ticker"]},
        description="A mock tool",
    )

    result = reg.call("mock_tool", "NVDA", "2026-03-28")
    assert result == "result for NVDA"


def test_registry_call_many():
    """call_many should return results for all registered tools."""
    from openclaw.tool_registry import ToolRegistry

    reg = ToolRegistry()
    reg.register("tool_a", fn=lambda: "A", param_builder=lambda _: {}, description="A")
    reg.register("tool_b", fn=lambda: "B", param_builder=lambda _: {}, description="B")

    results = reg.call_many(["tool_a", "tool_b"], "NVDA", "2026-03-28")
    assert results == {"tool_a": "A", "tool_b": "B"}


def test_registry_call_many_handles_missing():
    """call_many should skip unregistered tools gracefully."""
    from openclaw.tool_registry import ToolRegistry

    reg = ToolRegistry()
    reg.register("tool_a", fn=lambda: "A", param_builder=lambda _: {}, description="A")

    results = reg.call_many(["tool_a", "nonexistent"], "NVDA", "2026-03-28")
    assert "tool_a" in results
    assert "nonexistent" not in results


def test_registry_call_many_handles_errors():
    """call_many should catch tool errors and return error string."""
    from openclaw.tool_registry import ToolRegistry

    def failing():
        raise ValueError("API down")

    reg = ToolRegistry()
    reg.register("broken", fn=failing, param_builder=lambda _: {}, description="broken")

    results = reg.call_many(["broken"], "NVDA", "2026-03-28")
    assert "broken" in results
    assert "Data unavailable" in results["broken"]


def test_registry_describe_all():
    """describe_all should list all tools with descriptions."""
    from openclaw.tool_registry import ToolRegistry

    reg = ToolRegistry()
    reg.register("tool_x", fn=lambda: "", param_builder=lambda _: {}, description="Does X", category="test")

    desc = reg.describe_all()
    assert "tool_x" in desc
    assert "Does X" in desc
    assert "test" in desc


def test_registry_list_by_category():
    """list_by_category should filter tools."""
    from openclaw.tool_registry import registry
    import openclaw.tools

    stock_tools = registry.list_by_category("stock")
    assert "get_stock_data" in stock_tools

    news_tools = registry.list_by_category("news")
    assert "get_news" in news_tools
