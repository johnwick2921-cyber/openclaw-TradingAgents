# Trading Day-Cycle

### Pre-Session (before market open, ~8:00 AM ET)
- Check halt flag
- Run full analysis for watchlist tickers
- Record signals in memory

### During Session (market hours, every ~30 min)
- Fetch current prices (no LLM)
- Compare to morning predictions

### Post-Session (after market close, ~4:30 PM ET)
- Fetch actual closing prices
- Compare predictions vs reality
- Run reflection with outcome data
- Persist memories
