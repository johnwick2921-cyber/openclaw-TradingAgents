# Trading Rules

## Risk Parameters
Risk parameters are loaded from trading-config.json and are non-negotiable.
The system enforces: max loss per trade, daily loss limit, max drawdown,
max consecutive losses, and minimum risk/reward ratio.

These values are set by the trader and cannot be overridden by any agent.

## Active Strategy
The current strategy is set in trading-config.json.
Strategies define which analysts run, which indicators to use, and which
entry models to apply. The strategy may be "stocks" or "jadecap" or others.

Your PROMPT.md contains the strategy-specific instructions.
Follow them exactly — they define your methodology for the current strategy.

## Constraint
Analysis only — no order execution, no positions, no broker connection.
