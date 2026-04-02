# HEARTBEAT.md Template

```markdown
# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.
```

## Trading Day-Cycle

### Pre-Session (before market open, ~8:00 AM ET)
- [ ] Check halt flag in trading-config.json
- [ ] Run full analysis for each ticker in watchlist
- [ ] Record signals in memory/YYYY-MM-DD.md

### During Session (market hours, every ~30 min)
- [ ] Fetch current prices for analyzed tickers (yfinance, no LLM)
- [ ] Compare to morning predictions
- [ ] Append price updates to memory/YYYY-MM-DD.md
- [ ] Check data provider health

### Post-Session (after market close, ~4:30 PM ET)
- [ ] Fetch actual closing prices for each analyzed ticker
- [ ] Compare predictions vs reality (signal correct?)
- [ ] Run enhanced reflection with outcome data
- [ ] Persist enriched memories to trading.db
- [ ] Curate key lessons into MEMORY.md
