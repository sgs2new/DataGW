"""
Trading Desk Indicator Engine V1
Specification: Trading_Desk_Indicator_Engine_Specification_v1.0
Interface: DGW2-TD-IF-1.0

Pure, deterministic technical-indicator calculation layer.

Rules:
- No network access
- No Yahoo Finance dependency
- No external market data
- No data repair
- No timeframe fallback
- No trading interpretation
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


# ============================================================
# Supported markets / intervals
# ============================================================

SUPPORTED_MARKETS = (
    "gold",
    "silver",
    "brent",
    "dax",
    "sp500",
    "nasdaq100",
    "dowjones",
)

SUPPORTED_INTERVALS = (
    "1d",
    "1wk",
    "1mo",
)


# ============================================================
# Indicator availability matrix
# ============================================================

INDICATOR_INTERVALS = {
    "SMA20": ("1d", "1wk", "1mo"),
    "SMA50": ("1d", "1wk", "1mo"),
    "SMA200": ("1d", "1wk", "1mo"),
    "EMA20": ("1d", "1wk", "1mo"),
    "EMA50": ("1d", "1wk", "1mo"),
    "RSI14": ("1d", "1wk", "1mo"),
    "MACD": ("1d", "1wk", "1mo"),
    "ROC12": ("1d", "1wk"),
    "ATR14": ("1d", "1wk", "1mo"),
    "BOLLINGER20": ("1d",),
    "PIVOT_DAILY": ("1d",),
}


# ============================================================
# Status model
# ============================================================

STATUS_CALCULATED = "CALCULATED"
STATUS_INSUFFICIENT = "INSUFFICIENT_HISTORY"
STATUS_INVALID = "INVALID_DATA"
STATUS_NOT_AVAILABLE = "NOT_AVAILABLE"
STATUS_ERROR = "ERROR"


# ============================================================
# Data structures
# ============================================================

@dataclass(frozen=True)
class Candle:
    timestamp: int
    datetime_utc: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class IndicatorResult:
    indicator: str
    interval: str
    parameters: dict[str, Any]
    value: Any
    status: str
    data_points_used: int
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# Utility
# ============================================================

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(
    indicator: str,
    interval: str,
    parameters: dict[str, Any],
    value: Any,
    status: str,
    data_points_used: int,
) -> IndicatorResult:

    return IndicatorResult(
        indicator=indicator,
        interval=interval,
        parameters=parameters,
        value=value,
        status=status,
        data_points_used=data_points_used,
        calculated_at=_now_utc(),
    )


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


# ============================================================
# DataGW candle validation
# ============================================================

def validate_candles(
    candles: Sequence[Candle],
) -> bool:
    """
    Defensive validation of DataGW candle data.

    The function never repairs, removes or reorders candles.
    """

    if not candles:
        return False

    seen: set[int] = set()
    previous_timestamp: int | None = None

    for candle in candles:

        # Timestamp
        if (
            not isinstance(candle.timestamp, int)
            or candle.timestamp <= 0
        ):
            return False

        # Duplicate timestamp
        if candle.timestamp in seen:
            return False

        seen.add(candle.timestamp)

        # Chronology
        if (
            previous_timestamp is not None
            and candle.timestamp <= previous_timestamp
        ):
            return False

        previous_timestamp = candle.timestamp

        # datetime
        if (
            not isinstance(candle.datetime_utc, str)
            or not candle.datetime_utc
        ):
            return False

        # Numeric OHLC
        for value in (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
        ):
            if (
                not _is_finite_number(value)
                or float(value) <= 0
            ):
                return False

        # OHLC relationship
        if not (
            candle.low
            <= candle.open
            <= candle.high
        ):
            return False

        if not (
            candle.low
            <= candle.close
            <= candle.high
        ):
            return False

        if not (
            candle.low
            <= candle.high
        ):
            return False

    return True


# ============================================================
# DataGW adapter
# ============================================================

def candles_from_datagw(
    payload: dict[str, Any],
    interval: str,
) -> list[Candle]:
    """
    Extract candles from a DataGW V2 market JSON payload.

    No repair, filtering or reordering is performed.
    """

    intervals = payload.get("intervals")

    if (
        not isinstance(intervals, dict)
        or interval not in intervals
    ):
        raise KeyError(
            f"Intervall nicht verfügbar: {interval}"
        )

    raw = intervals[interval].get("candles")

    if not isinstance(raw, list):
        raise ValueError(
            "candles ist keine Liste"
        )

    candles: list[Candle] = []

    for item in raw:

        try:

            candles.append(
                Candle(
                    timestamp=item["timestamp"],
                    datetime_utc=item["datetime_utc"],
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                )
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                f"Ungültige Candle-Struktur: {exc}"
            ) from exc

    return candles


# ============================================================
# Common calculation guard
# ============================================================

def _guard(
    indicator: str,
    interval: str,
    candles: Sequence[Candle],
    minimum: int,
    parameters: dict[str, Any],
) -> IndicatorResult | None:

    # Unsupported interval
    if interval not in SUPPORTED_INTERVALS:

        return _result(
            indicator,
            interval,
            parameters,
            None,
            STATUS_NOT_AVAILABLE,
            len(candles),
        )

    # Indicator not available on interval
    allowed = INDICATOR_INTERVALS.get(
        indicator,
        (),
    )

    if interval not in allowed:

        return _result(
            indicator,
            interval,
            parameters,
            None,
            STATUS_NOT_AVAILABLE,
            len(candles),
        )

    # Invalid source data
    if not validate_candles(candles):

        return _result(
            indicator,
            interval,
            parameters,
            None,
            STATUS_INVALID,
            len(candles),
        )

    # Insufficient production history
    if len(candles) < minimum:

        return _result(
            indicator,
            interval,
            parameters,
            None,
            STATUS_INSUFFICIENT,
            len(candles),
        )

    return None


# ============================================================
# SMA
# ============================================================

def _sma_values(
    values: Sequence[float],
    period: int,
) -> list[float]:

    if len(values) < period:
        return []

    window_sum = sum(
        values[:period]
    )

    result = [
        window_sum / period
    ]

    for i in range(
        period,
        len(values),
    ):

        window_sum += (
            values[i]
            - values[i - period]
        )

        result.append(
            window_sum / period
        )

    return result


def sma(
    candles: Sequence[Candle],
    interval: str,
    period: int,
) -> IndicatorResult:

    indicator = f"SMA{period}"

    params = {
        "period": period
    }

    guard = _guard(
        indicator,
        interval,
        candles,
        period,
        params,
    )

    if guard:
        return guard

    values = [
        candle.close
        for candle in candles
    ]

    value = _sma_values(
        values,
        period,
    )[-1]

    return _result(
        indicator,
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# EMA
# ============================================================

def _ema_values(
    values: Sequence[float],
    period: int,
) -> list[float]:

    if len(values) < period:
        return []

    multiplier = (
        2.0
        / (period + 1.0)
    )

    # Initial EMA seed = SMA(period)
    ema = (
        sum(values[:period])
        / period
    )

    result = [ema]

    for value in values[period:]:

        ema = (
            (value - ema)
            * multiplier
            + ema
        )

        result.append(ema)

    return result


def ema(
    candles: Sequence[Candle],
    interval: str,
    period: int,
    production_warmup: int,
) -> IndicatorResult:

    indicator = f"EMA{period}"

    params = {
        "period": period,
        "warmup": production_warmup,
    }

    guard = _guard(
        indicator,
        interval,
        candles,
        production_warmup,
        params,
    )

    if guard:
        return guard

    values = [
        candle.close
        for candle in candles
    ]

    value = _ema_values(
        values,
        period,
    )[-1]

    return _result(
        indicator,
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# RSI14
# ============================================================

def rsi14(
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    period = 14
    indicator = "RSI14"

    params = {
        "period": period
    }

    guard = _guard(
        indicator,
        interval,
        candles,
        period + 1,
        params,
    )

    if guard:
        return guard

    closes = [
        candle.close
        for candle in candles
    ]

    changes = [
        closes[i]
        - closes[i - 1]
        for i in range(
            1,
            len(closes),
        )
    ]

    gains = [
        max(change, 0.0)
        for change in changes
    ]

    losses = [
        max(-change, 0.0)
        for change in changes
    ]

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    # Wilder smoothing
    for i in range(
        period,
        len(gains),
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
            )
            + losses[i]
        ) / period

    if avg_loss == 0:

        value = (
            100.0
            if avg_gain > 0
            else 50.0
        )

    elif avg_gain == 0:

        value = 0.0

    else:

        rs = (
            avg_gain
            / avg_loss
        )

        value = (
            100.0
            - (
                100.0
                / (1.0 + rs)
            )
        )

    return _result(
        indicator,
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# MACD 12/26/9
# ============================================================

def macd(
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    params = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "minimum_production_history": 60,
    }

    guard = _guard(
        "MACD",
        interval,
        candles,
        60,
        params,
    )

    if guard:
        return guard

    closes = [
        candle.close
        for candle in candles
    ]

    fast_period = 12
    slow_period = 26
    signal_period = 9

    fast_multiplier = (
        2.0
        / (fast_period + 1.0)
    )

    slow_multiplier = (
        2.0
        / (slow_period + 1.0)
    )

    signal_multiplier = (
        2.0
        / (signal_period + 1.0)
    )

    fast_ema = (
        sum(closes[:fast_period])
        / fast_period
    )

    slow_ema = (
        sum(closes[:slow_period])
        / slow_period
    )

    macd_series: list[float] = []

    for i, close in enumerate(
        closes
    ):

        if i >= fast_period:

            fast_ema = (
                (
                    close
                    - fast_ema
                )
                * fast_multiplier
                + fast_ema
            )

        if i >= slow_period:

            slow_ema = (
                (
                    close
                    - slow_ema
                )
                * slow_multiplier
                + slow_ema
            )

        if i >= slow_period - 1:

            macd_series.append(
                fast_ema - slow_ema
            )

    if (
        len(macd_series)
        < signal_period
    ):

        return _result(
            "MACD",
            interval,
            params,
            None,
            STATUS_INSUFFICIENT,
            len(candles),
        )

    signal_ema = (
        sum(
            macd_series[
                :signal_period
            ]
        )
        / signal_period
    )

    for macd_value in (
        macd_series[
            signal_period:
        ]
    ):

        signal_ema = (
            (
                macd_value
                - signal_ema
            )
            * signal_multiplier
            + signal_ema
        )

    macd_value = macd_series[-1]

    histogram = (
        macd_value
        - signal_ema
    )

    value = {
        "macd": macd_value,
        "signal": signal_ema,
        "histogram": histogram,
    }

    return _result(
        "MACD",
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# ROC12
# ============================================================

def roc12(
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    period = 12
    indicator = "ROC12"

    params = {
        "period": period
    }

    guard = _guard(
        indicator,
        interval,
        candles,
        period + 1,
        params,
    )

    if guard:
        return guard

    current = candles[-1].close

    previous = candles[
        -(period + 1)
    ].close

    if previous == 0:

        return _result(
            indicator,
            interval,
            params,
            None,
            STATUS_ERROR,
            len(candles),
        )

    value = (
        (
            current
            / previous
        )
        - 1.0
    ) * 100.0

    return _result(
        indicator,
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# ATR14
# ============================================================

def atr14(
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    period = 14
    indicator = "ATR14"

    params = {
        "period": period
    }

    guard = _guard(
        indicator,
        interval,
        candles,
        period + 1,
        params,
    )

    if guard:
        return guard

    true_ranges: list[float] = []

    for i in range(
        1,
        len(candles),
    ):

        current = candles[i]
        previous_close = (
            candles[i - 1].close
        )

        true_range = max(
            current.high
            - current.low,

            abs(
                current.high
                - previous_close
            ),

            abs(
                current.low
                - previous_close
            ),
        )

        true_ranges.append(
            true_range
        )

    atr = (
        sum(true_ranges[:period])
        / period
    )

    # Wilder smoothing
    for true_range in (
        true_ranges[period:]
    ):

        atr = (
            (
                atr
                * (period - 1)
            )
            + true_range
        ) / period

    close = candles[-1].close

    atr_percent = (
        atr
        / close
        * 100.0
        if close != 0
        else math.inf
    )

    if (
        not math.isfinite(atr)
        or not math.isfinite(
            atr_percent
        )
    ):

        return _result(
            indicator,
            interval,
            params,
            None,
            STATUS_ERROR,
            len(candles),
        )

    value = {
        "atr": atr,
        "atr_percent": atr_percent,
    }

    return _result(
        indicator,
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# Bollinger Bands 20/2
# ============================================================

def bollinger20(
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    period = 20
    standard_deviation = 2.0

    indicator = "BOLLINGER20"

    params = {
        "period": period,
        "standard_deviation":
            standard_deviation,
    }

    guard = _guard(
        indicator,
        interval,
        candles,
        period,
        params,
    )

    if guard:
        return guard

    closes = [
        candle.close
        for candle in candles[
            -period:
        ]
    ]

    middle = (
        sum(closes)
        / period
    )

    variance = (
        sum(
            (
                value - middle
            ) ** 2
            for value in closes
        )
        / period
    )

    sigma = math.sqrt(
        variance
    )

    upper = (
        middle
        + standard_deviation
        * sigma
    )

    lower = (
        middle
        - standard_deviation
        * sigma
    )

    if middle != 0:

        width = (
            (
                upper
                - lower
            )
            / middle
        ) * 100.0

    else:

        width = 0.0

    if upper != lower:

        position = (
            closes[-1]
            - lower
        ) / (
            upper
            - lower
        )

    else:

        position = 0.5

    value = {
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "width": width,
        "position": position,
    }

    return _result(
        indicator,
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# Daily Pivot Points
# ============================================================

def daily_pivot(
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    params = {
        "type": "daily",
        "source":
            "previous_completed_daily_candle",
    }

    guard = _guard(
        "PIVOT_DAILY",
        interval,
        candles,
        2,
        params,
    )

    if guard:
        return guard

    # Previous completed daily candle
    previous = candles[-2]

    high = previous.high
    low = previous.low
    close = previous.close

    pivot = (
        high
        + low
        + close
    ) / 3.0

    r1 = (
        2.0 * pivot
        - low
    )

    s1 = (
        2.0 * pivot
        - high
    )

    r2 = (
        pivot
        + (high - low)
    )

    s2 = (
        pivot
        - (high - low)
    )

    r3 = (
        high
        + 2.0
        * (pivot - low)
    )

    s3 = (
        low
        - 2.0
        * (high - pivot)
    )

    value = {
        "pivot": pivot,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "s1": s1,
        "s2": s2,
        "s3": s3,
    }

    return _result(
        "PIVOT_DAILY",
        interval,
        params,
        value,
        STATUS_CALCULATED,
        len(candles),
    )


# ============================================================
# Indicator dispatcher
# ============================================================

def calculate_indicator(
    indicator: str,
    candles: Sequence[Candle],
    interval: str,
) -> IndicatorResult:

    dispatch = {

        "SMA20":
            lambda: sma(
                candles,
                interval,
                20,
            ),

        "SMA50":
            lambda: sma(
                candles,
                interval,
                50,
            ),

        "SMA200":
            lambda: sma(
                candles,
                interval,
                200,
            ),

        "EMA20":
            lambda: ema(
                candles,
                interval,
                20,
                50,
            ),

        "EMA50":
            lambda: ema(
                candles,
                interval,
                50,
                100,
            ),

        "RSI14":
            lambda: rsi14(
                candles,
                interval,
            ),

        "MACD":
            lambda: macd(
                candles,
                interval,
            ),

        "ROC12":
            lambda: roc12(
                candles,
                interval,
            ),

        "ATR14":
            lambda: atr14(
                candles,
                interval,
            ),

        "BOLLINGER20":
            lambda: bollinger20(
                candles,
                interval,
            ),

        "PIVOT_DAILY":
            lambda: daily_pivot(
                candles,
                interval,
            ),
    }

    if indicator not in dispatch:

        return _result(
            indicator,
            interval,
            {},
            None,
            STATUS_NOT_AVAILABLE,
            len(candles),
        )

    try:

        return dispatch[indicator]()

    except Exception:

        return _result(
            indicator,
            interval,
            {},
            None,
            STATUS_ERROR,
            len(candles),
        )


# ============================================================
# Calculate all permitted indicators
# ============================================================

def calculate_all(
    candles: Sequence[Candle],
    interval: str,
) -> dict[str, IndicatorResult]:

    return {
        indicator:
            calculate_indicator(
                indicator,
                candles,
                interval,
            )

        for indicator, intervals
        in INDICATOR_INTERVALS.items()

        if interval in intervals
    }


# ============================================================
# JSON helpers
# ============================================================

def load_market_json(
    path: Path,
) -> dict[str, Any]:

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(handle)


def calculate_market_file(
    path: Path,
) -> dict[str, Any]:

    payload = load_market_json(
        path
    )

    output: dict[str, Any] = {
        "market_id": path.stem,
        "indicators": {},
    }

    for interval in (
        SUPPORTED_INTERVALS
    ):

        try:

            candles = (
                candles_from_datagw(
                    payload,
                    interval,
                )
            )

        except KeyError:

            output[
                "indicators"
            ][interval] = {}

            continue

        results = calculate_all(
            candles,
            interval,
        )

        output[
            "indicators"
        ][interval] = {
            name:
                result.to_dict()

            for name, result
            in results.items()
        }

    return output


# ============================================================
# Command line interface
# ============================================================

def _main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Trading Desk "
            "Indicator Engine V1"
        )
    )

    parser.add_argument(
        "market_json",
        type=Path,
        help="DataGW V2 market JSON",
    )

    parser.add_argument(
        "--interval",
        choices=SUPPORTED_INTERVALS,
        help=(
            "Only calculate "
            "one interval"
        ),
    )

    args = parser.parse_args()

    payload = load_market_json(
        args.market_json
    )

    intervals = (
        (args.interval,)
        if args.interval
        else SUPPORTED_INTERVALS
    )

    output: dict[str, Any] = {
        "market_id":
            args.market_json.stem,
        "indicators": {},
    }

    for interval in intervals:

        try:

            candles = (
                candles_from_datagw(
                    payload,
                    interval,
                )
            )

        except KeyError:

            output[
                "indicators"
            ][interval] = {}

            continue

        output[
            "indicators"
        ][interval] = {
            name:
                result.to_dict()

            for name, result
            in calculate_all(
                candles,
                interval,
            ).items()
        }

    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        _main()
    )
