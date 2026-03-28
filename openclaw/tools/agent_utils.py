# Import tools from separate utility files
from openclaw.tools.core_stock_tools import get_stock_data
from openclaw.tools.technical_indicators_tools import get_indicators
from openclaw.tools.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from openclaw.tools.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news,
)


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder.
        In the subagent architecture, message clearing is handled by the RunEngine.
        Kept for backward compatibility.
        """
        return {"messages": [{"role": "user", "content": "Continue"}]}

    return delete_messages
