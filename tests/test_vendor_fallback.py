import pytest
from unittest.mock import patch, MagicMock
from openclaw.dataflows.interface import route_to_vendor


def test_fallback_on_network_error():
    """Vendor fallback should trigger on any exception, not just AlphaVantageRateLimitError."""
    with patch("openclaw.dataflows.interface.get_config") as mock_config:
        mock_config.return_value = {
            "data_vendors": {"core_stock_apis": "alpha_vantage"},
            "tool_vendors": {},
        }
        with patch("openclaw.dataflows.interface.VENDOR_METHODS", {
            "get_stock_data": {
                "alpha_vantage": MagicMock(side_effect=ConnectionError("timeout")),
                "yfinance": MagicMock(return_value="yfinance_data"),
            }
        }):
            result = route_to_vendor("get_stock_data", "AAPL", "2026-03-27")
            assert result == "yfinance_data"


def test_fallback_on_auth_error():
    """Vendor fallback should trigger on authentication errors."""
    with patch("openclaw.dataflows.interface.get_config") as mock_config:
        mock_config.return_value = {
            "data_vendors": {"core_stock_apis": "alpha_vantage"},
            "tool_vendors": {},
        }
        with patch("openclaw.dataflows.interface.VENDOR_METHODS", {
            "get_stock_data": {
                "alpha_vantage": MagicMock(side_effect=PermissionError("bad key")),
                "yfinance": MagicMock(return_value="yfinance_data"),
            }
        }):
            result = route_to_vendor("get_stock_data", "AAPL", "2026-03-27")
            assert result == "yfinance_data"


def test_all_vendors_fail_raises():
    """When all vendors fail, RuntimeError should be raised."""
    with patch("openclaw.dataflows.interface.get_config") as mock_config:
        mock_config.return_value = {
            "data_vendors": {"core_stock_apis": "yfinance"},
            "tool_vendors": {},
        }
        with patch("openclaw.dataflows.interface.VENDOR_METHODS", {
            "get_stock_data": {
                "yfinance": MagicMock(side_effect=ConnectionError("down")),
            }
        }):
            with pytest.raises(RuntimeError, match="No available vendor"):
                route_to_vendor("get_stock_data", "AAPL", "2026-03-27")
