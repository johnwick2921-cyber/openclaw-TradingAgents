# Trading Rules

## Risk Parameters
Risk parameters are loaded LIVE from trading-config.json on every run.
Do NOT use hardcoded values — the numbers below are examples only.
The actual values are injected into your prompt by the RunEngine.

These are NON-NEGOTIABLE — no agent can override them.

## Active Strategy
Strategy is set by the user in trading-config.json ("stocks" or "jadecap").
Your PROMPT.md contains strategy-specific instructions.
The instrument (NQ, ES, NVDA, etc.) comes from the user's analysis request — not from config.

## Constraint
Analysis only — no order execution, no positions, no broker connection.
