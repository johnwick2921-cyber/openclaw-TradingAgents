"""Verify ICT indicator functions work with lowercase column names."""

import pandas as pd
import pytest


def test_displacement_candle_lowercase_columns():
    """calc_displacement_candle should work with lowercase column names."""
    from openclaw.indicators import calc_displacement_candle

    df = pd.DataFrame({
        "open": [100.0, 101.0, 105.0, 103.0, 108.0],
        "high": [102.0, 106.0, 110.0, 107.0, 112.0],
        "low": [99.0, 100.0, 104.0, 102.0, 106.0],
        "close": [101.0, 105.0, 109.0, 106.0, 111.0],
        "volume": [1000, 1200, 1500, 1100, 1800],
    }, index=pd.date_range("2026-03-23", periods=5, freq="1D"))

    result = calc_displacement_candle(df)
    assert result is not None


def test_liquidity_sweep_lowercase_columns():
    """calc_liquidity_sweep should work with lowercase column names."""
    from openclaw.indicators import calc_liquidity_sweep

    df = pd.DataFrame({
        "open": [100.0, 101.0, 99.0, 102.0, 103.0],
        "high": [102.0, 103.0, 101.0, 104.0, 105.0],
        "low": [99.0, 100.0, 97.0, 101.0, 102.0],
        "close": [101.0, 102.0, 100.0, 103.0, 104.0],
        "volume": [1000, 1200, 1500, 1100, 1800],
    }, index=pd.date_range("2026-03-23", periods=5, freq="1D"))

    result = calc_liquidity_sweep(df)
    assert result is not None


def test_breaker_block_lowercase_columns():
    """calc_breaker_block should work with lowercase column names."""
    from openclaw.indicators import calc_breaker_block

    df = pd.DataFrame({
        "open": [100.0, 103.0, 101.0, 104.0, 102.0, 105.0],
        "high": [104.0, 105.0, 103.0, 106.0, 104.0, 107.0],
        "low": [99.0, 101.0, 99.0, 102.0, 100.0, 103.0],
        "close": [103.0, 102.0, 102.0, 105.0, 103.0, 106.0],
        "volume": [1000, 1200, 1500, 1100, 1800, 2000],
    }, index=pd.date_range("2026-03-22", periods=6, freq="1D"))

    result = calc_breaker_block(df)
    assert result is not None
