"""Dynamic tool registry for OpenClaw trading pipeline.

Tools register themselves with a name, callable, and a param_builder
that maps standard context (ticker, date, config) into tool-specific kwargs.

Usage:
    from openclaw.tool_registry import registry

    # Register a tool
    registry.register(
        name="get_stock_data",
        fn=get_stock_data,
        param_builder=lambda ctx: {"symbol": ctx["ticker"], "start_date": ctx["start_30d"], "end_date": ctx["date"]},
        description="Fetch OHLCV price history",
    )

    # Call a tool by name
    result = registry.call("get_stock_data", ticker="NVDA", date="2026-03-28")

    # List all tools
    registry.list_tools()  # ["get_stock_data", "get_indicators", ...]
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _build_context(ticker: str, date: str, config: Optional[dict] = None) -> dict:
    """Build standard context dict from ticker + date.

    Every tool param_builder receives this context to derive its arguments.
    """
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    return {
        "ticker": ticker,
        "date": date,
        "start_7d": (date_obj - timedelta(days=7)).strftime("%Y-%m-%d"),
        "start_30d": (date_obj - timedelta(days=30)).strftime("%Y-%m-%d"),
        "start_90d": (date_obj - timedelta(days=90)).strftime("%Y-%m-%d"),
        "config": config or {},
    }


class ToolRegistry:
    """Central registry for all callable tools in the trading pipeline."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def register(
        self,
        name: str,
        fn: Callable,
        param_builder: Callable[[dict], dict],
        description: str = "",
        category: str = "general",
    ) -> None:
        """Register a tool.

        Args:
            name: Tool name as referenced in agent .md frontmatter.
            fn: The Python callable to execute.
            param_builder: Function(context) -> kwargs dict for fn.
            description: Human-readable description.
            category: Tool category (stock, technical, fundamental, news, ict).
        """
        self._tools[name] = {
            "fn": fn,
            "param_builder": param_builder,
            "description": description,
            "category": category,
        }

    def call(self, name: str, ticker: str, date: str, config: Optional[dict] = None) -> str:
        """Call a registered tool by name.

        Args:
            name: Tool name.
            ticker: Instrument symbol.
            date: Trade date (YYYY-MM-DD).
            config: Optional config dict for tools that need it.

        Returns:
            Tool output as string.

        Raises:
            KeyError: If tool name is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(self._tools.keys())}")

        tool = self._tools[name]
        ctx = _build_context(ticker, date, config)
        kwargs = tool["param_builder"](ctx)
        return tool["fn"](**kwargs)

    def call_many(self, names: List[str], ticker: str, date: str,
                  config: Optional[dict] = None) -> Dict[str, str]:
        """Call multiple tools, returning results keyed by tool name.

        Failed tools are logged and returned as error strings.
        """
        results = {}
        for name in names:
            try:
                results[name] = self.call(name, ticker, date, config)
            except KeyError:
                logger.warning("Tool '%s' not registered, skipping", name)
            except Exception as exc:
                logger.warning("Tool '%s' failed for %s: %s", name, ticker, exc)
                results[name] = f"[Data unavailable: {exc}]"
        return results

    def list_tools(self) -> List[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> List[str]:
        """Return tool names filtered by category."""
        return [n for n, t in self._tools.items() if t["category"] == category]

    def get_info(self, name: str) -> Optional[dict]:
        """Get tool metadata (description, category). None if not found."""
        tool = self._tools.get(name)
        if not tool:
            return None
        return {"name": name, "description": tool["description"], "category": tool["category"]}

    def describe_all(self) -> str:
        """Return a formatted string describing all registered tools."""
        lines = []
        for name, tool in sorted(self._tools.items()):
            lines.append(f"- {name} [{tool['category']}]: {tool['description']}")
        return "\n".join(lines)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# Module-level singleton
registry = ToolRegistry()
