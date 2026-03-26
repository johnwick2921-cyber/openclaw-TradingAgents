"""Live price endpoint — Databento live stream with yfinance fallback."""

import asyncio
import json
import os
import logging
import threading
import warnings
from datetime import datetime, timedelta, timezone
from typing import Set

warnings.filterwarnings("ignore", module="databento")
warnings.filterwarnings("ignore", message=".*reduced quality.*")

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from webui.backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ── Global live price cache (updated by background stream) ──────────
_live_prices: dict = {}  # symbol -> {price, open, high, low, volume, ...}
_live_lock = threading.Lock()
_live_stream_started = False
_live_client = None

# ── WebSocket clients subscribed to price updates ──────────────────
_price_ws_clients: Set[WebSocket] = set()
_price_ws_lock = threading.Lock()
_event_loop = None  # set once at app startup via init_event_loop()


def init_event_loop(loop=None):
    """Capture the event loop once at app startup. Call from lifespan."""
    global _event_loop
    _event_loop = loop or asyncio.get_running_loop()


async def _get_configured_provider() -> str:
    """Read the data provider from Settings. Falls back to yfinance."""
    try:
        async with get_db() as db:
            row = await db.execute(
                "SELECT value FROM settings WHERE key = 'data_vendors'"
            )
            result = await row.fetchone()
            if result and result[0]:
                vendors = json.loads(result[0])
                return vendors.get("core_stock_apis", "yfinance")
    except Exception:
        pass
    return "yfinance"


# Futures symbols → Databento continuous contract (GLBX.MDP3 dataset)
_FUTURES_SYMBOLS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K",
    "CL", "MCL", "GC", "MGC", "SI", "SIL", "ZB", "ZN",
    "6E", "6J", "HG", "NG", "ZC", "ZS", "ZW",
}

# Map common ticker symbols to Databento symbols
_DATABENTO_SYMBOL_MAP = {
    # Futures → continuous contracts (GLBX.MDP3)
    "NQ": "NQ.c.0", "MNQ": "MNQ.c.0",
    "ES": "ES.c.0", "MES": "MES.c.0",
    "YM": "YM.c.0", "MYM": "MYM.c.0",
    "RTY": "RTY.c.0", "M2K": "M2K.c.0",
    "CL": "CL.c.0", "MCL": "MCL.c.0",
    "GC": "GC.c.0", "MGC": "MGC.c.0",
    "SI": "SI.c.0", "SIL": "SIL.c.0",
    "ZB": "ZB.c.0", "ZN": "ZN.c.0",
    "6E": "6E.c.0", "6J": "6J.c.0",
}

# Track which symbols are subscribed
_subscribed_symbols: set = set()


def _start_live_stream(symbols=None):
    """Start Databento live stream in background thread. Updates _live_prices on every trade.

    Args:
        symbols: List of ticker symbols to subscribe to (e.g. ["NQ", "ES"]).
                 Defaults to ["NQ", "MNQ"] if not provided.
    """
    global _live_stream_started, _live_client, _subscribed_symbols

    if symbols is None:
        symbols = ["NQ", "MNQ"]

    # Separate futures vs equities
    futures_db_syms = []
    equity_syms = []
    for sym in symbols:
        clean = sym.upper().replace("=F", "").strip()
        _subscribed_symbols.add(clean)
        if clean in _FUTURES_SYMBOLS or clean in _DATABENTO_SYMBOL_MAP:
            db_sym = _DATABENTO_SYMBOL_MAP.get(clean, f"{clean}.c.0")
            futures_db_syms.append(db_sym)
        else:
            equity_syms.append(clean)  # Stocks — not supported in live stream yet
    db_symbols = futures_db_syms  # Only futures go to GLBX.MDP3 live stream

    # Thread-safe check-and-set to prevent duplicate Databento connections
    with _live_lock:
        if _live_stream_started:
            return
        _live_stream_started = True

    api_key = os.environ.get("DATABENTO_API_KEY", "")
    if not api_key:
        _live_stream_started = False
        raise ValueError("DATABENTO_API_KEY not set")

    import databento as db

    def _run_stream():
        global _live_client, _live_stream_started
        try:
            client = db.Live(key=api_key)
            _live_client = client

            # Subscribe to live trades for all requested symbols
            client.subscribe(
                dataset="GLBX.MDP3",
                schema="trades",
                symbols=db_symbols,
                stype_in="continuous",
            )
            logger.info("Databento live stream subscribing to: %s", db_symbols)

            def _on_record(record):
                try:
                    # Only process TradeMsg records
                    if type(record).__name__ != 'TradeMsg':
                        return

                    # Databento prices are fixed-point — divide by 1e9
                    price = record.price / 1e9
                    if price <= 0:
                        return

                    # Determine symbol from instrument_id using symbology map
                    instrument_id = getattr(record, 'instrument_id', 0)
                    # Reverse lookup: find which of our subscribed symbols this instrument belongs to
                    key = None
                    # Try symbology map first
                    if hasattr(client, 'symbology_map'):
                        sym_map = client.symbology_map
                        mapped = sym_map.get(instrument_id)
                        if mapped:
                            raw = mapped if isinstance(mapped, str) else (mapped.get('raw', '') if isinstance(mapped, dict) else str(mapped))
                            # Match against our symbol map
                            for ticker, db_sym in _DATABENTO_SYMBOL_MAP.items():
                                if raw.upper().startswith(ticker.upper()):
                                    key = ticker
                                    break
                    # Fallback: skip record if we can't determine the symbol
                    if not key:
                        return

                    vol = int(getattr(record, 'size', 0) or 0)

                    with _live_lock:
                        prev = _live_prices.get(key, {})
                        prev_close = prev.get('prev_close', price)
                        day_open = prev.get('open', price)
                        day_high = max(prev.get('high', 0), price)
                        day_low = min(prev.get('low', 999999), price) if prev.get('low', 999999) > 0 else price

                        change = price - prev_close
                        change_pct = (change / prev_close * 100) if prev_close else 0

                        tick = {
                            'symbol': key,
                            'price': round(price, 2),
                            'open': round(day_open, 2),
                            'high': round(day_high, 2),
                            'low': round(day_low, 2),
                            'volume': vol,
                            'change': round(change, 2),
                            'change_pct': round(change_pct, 2),
                            'prev_close': round(prev_close, 2),
                            'source': 'databento (live)',
                            'updated': datetime.now(timezone.utc).isoformat() + 'Z',
                        }
                        _live_prices[key] = tick

                    # Broadcast to all WebSocket price subscribers
                    _broadcast_price(tick)

                except Exception as e:
                    logger.debug(f"Live price record error: {e}")

            client.add_callback(_on_record)
            client.start()
            logger.info("Databento live stream started for NQ, MNQ")
            client.block_for_close()
        except Exception as e:
            logger.error(f"Databento live stream failed: {e}")
            _live_stream_started = False

    thread = threading.Thread(target=_run_stream, daemon=True)
    thread.start()


def _get_price_databento(symbol: str) -> dict:
    """Get latest price from the live Databento stream cache."""
    clean = symbol.upper().replace("=F", "").strip()

    # Start stream for this symbol if not running
    if not _live_stream_started and clean in _FUTURES_SYMBOLS:
        _start_live_stream(symbols=[clean])
    elif clean not in _subscribed_symbols:
        # Not subscribed — fall through to Historical/yfinance
        raise ValueError(f"{clean} not in live stream")

    key = clean

    with _live_lock:
        cached = _live_prices.get(key)

    if cached:
        return cached

    # If live stream hasn't received data yet, fall back to Historical API
    return _get_price_databento_historical(key)


def _get_price_databento_historical(symbol: str) -> dict:
    """Fallback: get latest price from Databento Historical API (1-minute bars)."""
    import databento as dbn

    api_key = os.environ.get("DATABENTO_API_KEY", "")
    if not api_key:
        raise ValueError("DATABENTO_API_KEY not set")

    clean = symbol.upper().replace("=F", "").strip()
    db_sym = _DATABENTO_SYMBOL_MAP.get(clean, f"{clean}.c.0")

    client = dbn.Historical(key=api_key)
    # Historical data has ~10-15 min delay — query up to 15 min ago
    end = datetime.now(timezone.utc) - timedelta(minutes=15)
    start = end - timedelta(hours=2)

    data = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        schema="ohlcv-1m",
        symbols=[db_sym],
        stype_in="continuous",
        start=start.strftime("%Y-%m-%dT%H:%M"),
        end=end.strftime("%Y-%m-%dT%H:%M"),
        limit=120,
    )

    records = list(data)
    if not records:
        raise ValueError(f"No historical data for {db_sym}")

    latest = records[-1]
    price = latest.close / 1e9

    # Find prev session close for change calculation
    prev_close = price
    if len(records) > 60:
        prev_close = records[0].close / 1e9

    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0

    # Day high/low from all records
    day_high = max(r.high / 1e9 for r in records)
    day_low = min(r.low / 1e9 for r in records)
    day_open = records[0].open / 1e9
    total_vol = sum(r.volume for r in records)

    return {
        "symbol": clean,
        "price": round(price, 2),
        "open": round(day_open, 2),
        "high": round(day_high, 2),
        "low": round(day_low, 2),
        "volume": total_vol,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "prev_close": round(prev_close, 2),
        "source": "databento (historical 1m)",
        "updated": datetime.now(timezone.utc).isoformat() + "Z",
    }


def _get_price_alpha_vantage(symbol: str) -> dict:
    """Fetch latest price from Alpha Vantage."""
    import requests

    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY not set")

    resp = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key},
        timeout=10,
    )
    data = resp.json()
    quote = data.get("Global Quote", {})
    if not quote:
        raise ValueError(f"No quote for {symbol}")

    price = float(quote.get("05. price", 0))
    prev_close = float(quote.get("08. previous close", 0))
    change = float(quote.get("09. change", 0))
    change_pct = float(quote.get("10. change percent", "0").replace("%", ""))

    return {
        "symbol": symbol.upper(),
        "price": price,
        "open": float(quote.get("02. open", 0)),
        "high": float(quote.get("03. high", 0)),
        "low": float(quote.get("04. low", 0)),
        "volume": int(quote.get("06. volume", 0)),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "prev_close": prev_close,
        "source": "alpha_vantage",
        "updated": datetime.now(timezone.utc).isoformat() + "Z",
    }


def _get_price_yfinance(symbol: str) -> dict:
    """Fetch latest price from yfinance."""
    import yfinance as yf

    ticker = symbol.upper()
    if ticker in ("NQ", "ES", "CL", "GC", "YM", "RTY", "MNQ", "MES") and "=" not in ticker:
        ticker = f"{ticker}=F"

    t = yf.Ticker(ticker)
    hist = t.history(period="5d")
    if hist.empty:
        raise ValueError(f"No data for {ticker}")

    latest = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]

    close = float(latest["Close"])
    prev_close = float(prev["Close"])
    change = close - prev_close
    change_pct = (change / prev_close) * 100 if prev_close else 0

    return {
        "symbol": symbol.upper(),
        "price": close,
        "open": float(latest["Open"]),
        "high": float(latest["High"]),
        "low": float(latest["Low"]),
        "volume": int(latest["Volume"]),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "prev_close": prev_close,
        "source": "yfinance",
        "updated": datetime.now(timezone.utc).isoformat() + "Z",
    }


# Provider dispatch map
_PRICE_PROVIDERS = {
    "databento": _get_price_databento,
    "alpha_vantage": _get_price_alpha_vantage,
    "yfinance": _get_price_yfinance,
}


@router.get("/prices/{symbol}")
async def get_price(symbol: str) -> dict:
    """Get latest price. Always uses Databento for live data if key is set.
    Falls back to yfinance (delayed) only if Databento is unavailable."""

    # Live price = always Databento first (only source with real-time data)
    if os.environ.get("DATABENTO_API_KEY"):
        try:
            return _get_price_databento(symbol)
        except Exception as e:
            logger.debug(f"Databento live price failed for {symbol}: {e}")

    # Fallback to delayed sources
    for name in ("alpha_vantage", "yfinance"):
        try:
            result = _PRICE_PROVIDERS[name](symbol)
            result["source"] = f"{result['source']} (delayed)"
            return result
        except Exception as e:
            logger.debug(f"{name} price failed for {symbol}: {e}")

    return {
        "symbol": symbol.upper(),
        "price": None,
        "error": f"No price source available for {symbol}. Set DATABENTO_API_KEY for live data.",
        "updated": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.get("/prices/{symbol}/analysis")
async def get_analysis_price(symbol: str) -> dict:
    """Get price using the data provider configured in Settings (for analysis, not live)."""
    provider = await _get_configured_provider()

    if provider in _PRICE_PROVIDERS:
        try:
            return _PRICE_PROVIDERS[provider](symbol)
        except Exception as e:
            logger.debug(f"{provider} price failed for {symbol}: {e}")

    # Fallback chain
    for name, func in _PRICE_PROVIDERS.items():
        if name == provider:
            continue
        try:
            return func(symbol)
        except Exception as e:
            logger.debug(f"{name} price failed for {symbol}: {e}")

    return {
        "symbol": symbol.upper(),
        "price": None,
        "error": f"All providers failed for {symbol}",
        "updated": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ── Price broadcast to WebSocket clients ──────────────────────────

def _broadcast_price(tick: dict):
    """Push price tick to all connected WebSocket clients from the Databento thread."""
    with _price_ws_lock:
        clients = list(_price_ws_clients)
    if not clients or not _event_loop:
        return
    msg = json.dumps(tick)
    dead = []
    for ws in clients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), _event_loop)
        except Exception:
            dead.append(ws)
    if dead:
        with _price_ws_lock:
            for ws in dead:
                _price_ws_clients.discard(ws)


# ── WebSocket endpoint for live price streaming ───────────────────

# This is a separate router without /api prefix since WebSocket paths
# are registered on the main app
_ws_router = APIRouter()


@_ws_router.websocket("/ws/prices/{symbol}")
async def ws_price_stream(websocket: WebSocket, symbol: str):
    """Stream live price ticks via WebSocket. Falls back to polling if no Databento."""
    await websocket.accept()
    # Ensure event loop is captured (idempotent fallback if init_event_loop wasn't called)
    if _event_loop is None:
        init_event_loop()

    # Try to start Databento live stream
    has_databento = bool(os.environ.get("DATABENTO_API_KEY"))
    logger.info(f"Price WebSocket connected for {symbol}, Databento key: {has_databento}")
    if has_databento:
        try:
            _start_live_stream()
            logger.info(f"Databento live stream started: {_live_stream_started}")
        except Exception as e:
            logger.warning(f"Failed to start live stream: {e}")

    with _price_ws_lock:
        _price_ws_clients.add(websocket)

    try:
        # Send initial price immediately
        try:
            initial = await asyncio.to_thread(_get_price_for_ws, symbol)
            await websocket.send_json(initial)
        except Exception:
            logger.debug("Failed to send initial price for %s", symbol, exc_info=True)

        # Always poll as baseline — Databento live ticks override via broadcast
        # This ensures price updates even when live stream has no data (off-hours)
        while True:
            await asyncio.sleep(5)
            try:
                data = await asyncio.to_thread(_get_price_for_ws, symbol)
                await websocket.send_json(data)
            except Exception:
                logger.debug("Price poll failed for %s", symbol, exc_info=True)

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass  # Normal disconnection — no logging needed
    except Exception:
        logger.debug("WebSocket error for %s", symbol, exc_info=True)
    finally:
        with _price_ws_lock:
            _price_ws_clients.discard(websocket)


def _get_price_for_ws(symbol: str) -> dict:
    """Get price from any available source (called from WS handler)."""
    # Try Databento cache first
    clean = symbol.upper().replace("=F", "").strip()
    key = clean
    with _live_lock:
        cached = _live_prices.get(key)
    if cached:
        return cached

    # Try Databento Historical
    if os.environ.get("DATABENTO_API_KEY"):
        try:
            return _get_price_databento_historical(symbol)
        except Exception:
            logger.debug("Databento historical fallback failed for %s", symbol, exc_info=True)

    # Try yfinance
    try:
        return _get_price_yfinance(symbol)
    except Exception:
        logger.debug("yfinance fallback failed for %s", symbol, exc_info=True)

    return {"symbol": symbol, "price": None, "error": "No price source available"}
