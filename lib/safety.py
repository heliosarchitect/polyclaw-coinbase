"""Pre-trade safety checks and structured trade audit logging."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SafetyConfig:
    """Configurable safety controls."""

    trading_enabled: bool
    max_trade_usd: float
    min_market_liquidity_usd: float
    max_implied_slippage: float


@dataclass
class PreTradeRequest:
    """Input facts required for pre-trade checks."""

    market_id: str
    position: str
    amount_usd: float
    usdc_balance: float
    approvals_ok: bool
    market_active: bool
    market_closed: bool
    market_resolved: bool
    market_liquidity: float
    wanted_price: float
    unwanted_price: float


@dataclass
class PreTradeCheckResult:
    """Outcome of pre-trade validation."""

    ok: bool
    reasons: list[str]


def load_safety_config() -> SafetyConfig:
    """Load safety config from environment with strict defaults."""
    return SafetyConfig(
        trading_enabled=os.environ.get("POLYCLAW_TRADING_ENABLED", "false").lower() in {"1", "true", "yes"},
        max_trade_usd=float(os.environ.get("POLYCLAW_MAX_TRADE_USD", "25")),
        min_market_liquidity_usd=float(os.environ.get("POLYCLAW_MIN_MARKET_LIQUIDITY_USD", "1000")),
        max_implied_slippage=float(os.environ.get("POLYCLAW_MAX_IMPLIED_SLIPPAGE", "0.15")),
    )


def run_pretrade_checks(req: PreTradeRequest, cfg: SafetyConfig) -> PreTradeCheckResult:
    """Run invariant checks; block by default on any unsafe condition."""
    reasons: list[str] = []

    if not cfg.trading_enabled:
        reasons.append("global kill-switch enabled (POLYCLAW_TRADING_ENABLED=false)")

    if req.position not in {"YES", "NO"}:
        reasons.append("position must be YES or NO")

    if req.amount_usd <= 0:
        reasons.append("trade amount must be > 0")

    if req.amount_usd > cfg.max_trade_usd:
        reasons.append(
            f"trade amount {req.amount_usd:.2f} exceeds max {cfg.max_trade_usd:.2f}"
        )

    if req.usdc_balance < req.amount_usd:
        reasons.append(
            f"insufficient USDC.e: have {req.usdc_balance:.2f}, need {req.amount_usd:.2f}"
        )

    if not req.approvals_ok:
        reasons.append("required approvals missing")

    if not req.market_active or req.market_closed or req.market_resolved:
        reasons.append("market not tradable (inactive/closed/resolved)")

    if req.market_liquidity < cfg.min_market_liquidity_usd:
        reasons.append(
            f"market liquidity {req.market_liquidity:.2f} below minimum {cfg.min_market_liquidity_usd:.2f}"
        )

    implied_slippage = abs((req.wanted_price + req.unwanted_price) - 1.0)
    if implied_slippage > cfg.max_implied_slippage:
        reasons.append(
            f"implied slippage {implied_slippage:.4f} exceeds max {cfg.max_implied_slippage:.4f}"
        )

    return PreTradeCheckResult(ok=not reasons, reasons=reasons)


class TradeAuditLogger:
    """Append-only JSONL audit logger for trade lifecycle events."""

    def __init__(self, path: str | Path | None = None):
        default_path = Path(__file__).parent.parent / "logs" / "trade_audit.jsonl"
        self.path = Path(path) if path else default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, payload: dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")



def to_payload(obj: Any) -> dict[str, Any]:
    """Convert dataclass-ish objects to JSON payloads."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}
