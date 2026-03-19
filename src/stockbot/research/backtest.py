"""
Run deterministic strategy (INTRA_EVENT_MOMO) over historical bars.
Produces BacktestRun, BacktestTrade, BacktestSummary. No news in backtest (news_side=neutral).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from stockbot.db.models import BacktestRun, BacktestSummary, BacktestTrade
from stockbot.db.session import get_session_factory
from stockbot.research.datasets import fetch_bars_range
from stockbot.research.regimes import classify_regime_spy
from stockbot.strategies.intra_event_momo import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    FeatureSet,
    evaluate,
    exit_stop_target_prices,
)
from stockbot.strategies.state import BarLike, SymbolState


def run_backtest(
    *,
    strategy_id: str = STRATEGY_ID,
    strategy_version: str = STRATEGY_VERSION,
    symbols: list[str],
    start: datetime | str,
    end: datetime | str | None = None,
    feed: str = "iex",
    scrappy_mode: str = "advisory",
    ai_referee_mode: str = "off",
) -> str:
    """
    Fetch bars, run strategy, persist BacktestRun, BacktestTrade, BacktestSummary.
    Returns run_id.
    """
    run_id = str(uuid.uuid4())
    start_dt = start if isinstance(start, datetime) else datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = end if isinstance(end, datetime) else (datetime.fromisoformat(end.replace("Z", "+00:00")) if end else datetime.now(UTC))

    bars = fetch_bars_range(symbols, start_dt, end_dt, feed=feed)
    if not bars:
        factory = get_session_factory()
        import asyncio
        async def _empty_run():
            async with factory() as session:
                session.add(BacktestRun(
                    run_id=run_id,
                    strategy_id=strategy_id,
                    strategy_version=strategy_version,
                    symbols_json=symbols,
                    start_ts=start_dt,
                    end_ts=end_dt,
                    feed=feed,
                    scrappy_mode=scrappy_mode,
                    ai_referee_mode=ai_referee_mode,
                    status="completed",
                    notes="No bars returned",
                ))
                session.add(BacktestSummary(
                    run_id=run_id,
                    signal_count=0,
                    trade_count=0,
                    regime_label="sideways",
                    raw_json={},
                ))
                await session.commit()
        asyncio.run(_empty_run())
        return run_id

    state_by_symbol: dict[str, SymbolState] = {s: SymbolState(symbol=s) for s in symbols}
    last_close_by_symbol: dict[str, Decimal] = {}
    trades: list[dict[str, Any]] = []
    signal_count = 0
    position_by_symbol: dict[str, dict[str, Any]] = {}  # symbol -> {side, entry_ts, entry_price, stop, target, qty}

    entry_start_et = "09:35"
    entry_end_et = "11:30"
    force_flat_et = "15:45"

    def _et_after(ts: datetime, et_time: str) -> bool:
        try:
            import zoneinfo
            et = zoneinfo.ZoneInfo("America/New_York")
            return ts.astimezone(et).strftime("%H:%M") >= et_time
        except Exception:
            return False

    def _et_in_range(ts: datetime, start_et: str, end_et: str) -> bool:
        try:
            import zoneinfo
            et = zoneinfo.ZoneInfo("America/New_York")
            t_str = ts.astimezone(et).strftime("%H:%M")
            return start_et <= t_str <= end_et
        except Exception:
            return False

    for bar in bars:
        sym = bar.symbol
        if sym not in state_by_symbol:
            continue
        st = state_by_symbol[sym]
        if not st.prev_close and st.bars:
            st.prev_close = st.bars[0].open
        elif not st.prev_close:
            st.prev_close = bar.open
        st.bars.append(bar)
        if len(st.bars) > 200:
            st.bars = st.bars[-100:]
        st.latest_bid = bar.close
        st.latest_ask = bar.close
        st.latest_last = bar.close
        st.latest_quote_ts = bar.timestamp
        last_close_by_symbol[sym] = bar.close

        # Force flat
        if _et_after(bar.timestamp, force_flat_et) and sym in position_by_symbol:
            pos = position_by_symbol.pop(sym)
            exit_price = bar.close
            entry_price = pos["entry_price"]
            qty = pos["qty"]
            side = pos["side"]
            gross = (exit_price - entry_price) * qty if side == "buy" else (entry_price - exit_price) * qty
            trades.append({
                "symbol": sym,
                "side": side,
                "entry_ts": pos["entry_ts"],
                "exit_ts": bar.timestamp,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "qty": qty,
                "gross_pnl": gross,
                "net_pnl": gross,
                "exit_reason": "force_flat",
            })
            continue

        # Exit check for open position
        if sym in position_by_symbol:
            pos = position_by_symbol[sym]
            stop = pos["stop"]
            target = pos["target"]
            side = pos["side"]
            exit_price = None
            exit_reason = "open"
            if side == "buy":
                if bar.low <= stop:
                    exit_price = stop
                    exit_reason = "stop"
                elif bar.high >= target:
                    exit_price = target
                    exit_reason = "target"
            else:
                if bar.high >= stop:
                    exit_price = stop
                    exit_reason = "stop"
                elif bar.low <= target:
                    exit_price = target
                    exit_reason = "target"
            if exit_price is not None:
                pos = position_by_symbol.pop(sym)
                entry_price = pos["entry_price"]
                qty = pos["qty"]
                gross = (exit_price - entry_price) * qty if side == "buy" else (entry_price - exit_price) * qty
                trades.append({
                    "symbol": sym,
                    "side": side,
                    "entry_ts": pos["entry_ts"],
                    "exit_ts": bar.timestamp,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "qty": qty,
                    "gross_pnl": gross,
                    "net_pnl": gross,
                    "exit_reason": exit_reason,
                })
            continue

        or_high, or_low = st.opening_range()
        if or_high is None or or_low is None:
            continue
        prev_close = st.prev_close or (st.bars[0].open if st.bars else None)
        if prev_close is None:
            continue
        close = bar.close
        gap_pct = ((close - prev_close) / prev_close * 100).quantize(Decimal("0.01")) if prev_close else Decimal("0")
        spread_bps = 0
        minute_dollar = (bar.high + bar.low + bar.close) / 3 * bar.volume
        rel_vol = st.rel_volume_5m()
        features = FeatureSet(
            symbol=sym,
            ts=bar.timestamp,
            prev_close=prev_close,
            gap_pct_from_prev_close=gap_pct,
            spread_bps=spread_bps,
            minute_dollar_volume=minute_dollar,
            rel_volume_5m=rel_vol,
            opening_range_high=or_high,
            opening_range_low=or_low,
            session_vwap=st.session_vwap(),
            latest_bid=st.latest_bid,
            latest_ask=st.latest_ask,
            latest_last=st.latest_last,
            latest_minute_close=close,
            news_side="neutral",
            news_keyword_hits=[],
        )
        eval_result = evaluate(
            features,
            entry_start_et=entry_start_et,
            entry_end_et=entry_end_et,
            force_flat_et=force_flat_et,
        )
        if eval_result.side is None or not eval_result.passes_filters:
            continue
        signal_count += 1
        side_str = "buy" if eval_result.side == "buy" else "sell"
        entry_price = close
        stop_price, target_price = exit_stop_target_prices(eval_result.side, or_high, or_low, entry_price, 2.0)
        qty = Decimal("100")
        position_by_symbol[sym] = {
            "side": side_str,
            "entry_ts": bar.timestamp,
            "entry_price": entry_price,
            "stop": stop_price,
            "target": target_price,
            "qty": qty,
        }

    # Close any remaining positions at last bar
    last_ts = bars[-1].timestamp if bars else datetime.now(UTC)
    for sym, pos in list(position_by_symbol.items()):
        exit_price = last_close_by_symbol.get(sym, Decimal("0"))
        side = pos["side"]
        qty = pos["qty"]
        entry_price = pos["entry_price"]
        gross = (exit_price - entry_price) * qty if side == "buy" else (entry_price - exit_price) * qty
        trades.append({
            "symbol": sym,
            "side": side,
            "entry_ts": pos["entry_ts"],
            "exit_ts": last_ts,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": qty,
            "gross_pnl": gross,
            "net_pnl": gross,
            "exit_reason": "end_of_data",
        })

    # Regime from SPY
    regime = classify_regime_spy(bars, symbol="SPY", lookback_bars=20)

    # Summary stats
    win_count = sum(1 for t in trades if (t["net_pnl"] or 0) > 0)
    trade_count = len(trades)
    win_rate = (win_count / trade_count) if trade_count else None
    total_net = sum(t["net_pnl"] or 0 for t in trades)
    total_gross = sum(t["gross_pnl"] or 0 for t in trades)
    avg_return = (total_net / trade_count) if trade_count else None
    expectancy = avg_return

    async def _persist():
        factory = get_session_factory()
        async with factory() as session:
            session.add(BacktestRun(
                run_id=run_id,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                symbols_json=symbols,
                start_ts=start_dt,
                end_ts=end_dt,
                feed=feed,
                scrappy_mode=scrappy_mode,
                ai_referee_mode=ai_referee_mode,
                status="completed",
                notes=None,
            ))
            for t in trades:
                session.add(BacktestTrade(
                    run_id=run_id,
                    symbol=t["symbol"],
                    side=t["side"],
                    entry_ts=t["entry_ts"],
                    exit_ts=t["exit_ts"],
                    entry_price=t["entry_price"],
                    exit_price=t["exit_price"],
                    qty=t["qty"],
                    gross_pnl=t["gross_pnl"],
                    net_pnl=t["net_pnl"],
                    exit_reason=t["exit_reason"],
                    scrappy_mode=scrappy_mode,
                    ai_referee_mode=ai_referee_mode,
                    raw_json=t,
                ))
            session.add(BacktestSummary(
                run_id=run_id,
                signal_count=signal_count,
                trade_count=trade_count,
                win_rate=win_rate,
                avg_return_per_trade=avg_return,
                expectancy=expectancy,
                gross_pnl=total_gross,
                net_pnl=total_net,
                regime_label=regime,
                raw_json={"signal_count": signal_count, "trade_count": trade_count},
            ))
            await session.commit()

    import asyncio
    asyncio.run(_persist())
    return run_id
