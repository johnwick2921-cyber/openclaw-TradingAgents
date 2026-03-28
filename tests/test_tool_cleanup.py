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
    from openclaw.tools.core_stock_tools import get_stock_data
    assert type(get_stock_data).__name__ == "function", f"Expected function, got {type(get_stock_data)}"


def test_get_indicators_is_plain_function():
    from openclaw.tools.technical_indicators_tools import get_indicators
    assert type(get_indicators).__name__ == "function", f"Expected function, got {type(get_indicators)}"


def test_get_news_is_plain_function():
    from openclaw.tools.news_data_tools import get_news
    assert type(get_news).__name__ == "function", f"Expected function, got {type(get_news)}"


def test_get_fundamentals_is_plain_function():
    from openclaw.tools.fundamental_data_tools import get_fundamentals
    assert type(get_fundamentals).__name__ == "function", f"Expected function, got {type(get_fundamentals)}"
