import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# DataGW V2 - Yahoo Finance Market Data Fetcher
# ============================================================

INTERVALS = {
    "1d": {
        "interval": "1d",
        "range": "2y",
    },
    "1wk": {
        "interval": "1wk",
        "range": "5y",
    },
    "1mo": {
        "interval": "1mo",
        "range": "10y",
    },
}


# ============================================================
# Market configuration
# ============================================================

MARKETS = {
    "gold": {
        "symbol": "GC=F",
        "name": "Gold",
    },
    "silver": {
        "symbol": "SI=F",
        "name": "Silver",
    },
    "brent": {
        "symbol": "BZ=F",
        "name": "Brent",
    },
    "dax": {
        "symbol": "^GDAXI",
        "name": "DAX",
    },
    "sp500": {
        "symbol": "^GSPC",
        "name": "S&P 500",
    },
    "nasdaq100": {
        "symbol": "^NDX",
        "name": "Nasdaq 100",
    },
    "dowjones": {
        "symbol": "^DJI",
        "name": "Dow Jones",
    },
}


# ============================================================
# Yahoo Finance request
# ============================================================

def fetch_yahoo_data(symbol, interval, range_value):

    url = (
        "https://query2.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval={interval}&range={range_value}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return json.load(response)


# ============================================================
# Candle validation
# ============================================================

def validate_candle(candle):

    issues = []

    timestamp = candle.get("timestamp")
    datetime_utc = candle.get("datetime_utc")

    if timestamp is None:

        issues.append({
            "field": "timestamp",
            "reason": "missing"
        })

    if not datetime_utc:

        issues.append({
            "field": "datetime_utc",
            "reason": "missing"
        })

    open_price = candle.get("open")
    high_price = candle.get("high")
    low_price = candle.get("low")
    close_price = candle.get("close")

    prices = {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }

    for field, value in prices.items():

        if value is None:

            issues.append({
                "field": field,
                "reason": "missing"
            })

        elif value <= 0:

            issues.append({
                "field": field,
                "value": value,
                "reason": "must_be_greater_than_zero"
            })

    # OHLC relationship
    if all(
        value is not None
        for value in prices.values()
    ):

        if low_price > high_price:

            issues.append({
                "field": "low/high",
                "reason": "low_greater_than_high"
            })

        if not (
            low_price <= open_price <= high_price
        ):

            issues.append({
                "field": "open",
                "value": open_price,
                "reason": "outside_low_high_range"
            })

        if not (
            low_price <= close_price <= high_price
        ):

            issues.append({
                "field": "close",
                "value": close_price,
                "reason": "outside_low_high_range"
            })

    return issues


# ============================================================
# Extract and validate OHLC candles
# ============================================================

def extract_candles(data):

    result = data["chart"]["result"][0]

    timestamps = result.get(
        "timestamp",
        []
    )

    quote = result["indicators"]["quote"][0]

    candles = []
    invalid_candles = []

    previous_timestamp = None
    seen_timestamps = set()

    for i, timestamp in enumerate(timestamps):

        open_price = quote["open"][i]
        high_price = quote["high"][i]
        low_price = quote["low"][i]
        close_price = quote["close"][i]

        if timestamp is not None:

            datetime_utc = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            ).isoformat()

        else:

            datetime_utc = None

        candle = {
            "timestamp": timestamp,
            "datetime_utc": datetime_utc,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
        }

        issues = validate_candle(candle)

        # Duplicate timestamp
        if timestamp is not None:

            if timestamp in seen_timestamps:

                issues.append({
                    "field": "timestamp",
                    "value": timestamp,
                    "reason": "duplicate"
                })

            seen_timestamps.add(timestamp)

        # Chronological order
        if (
            timestamp is not None
            and previous_timestamp is not None
            and timestamp <= previous_timestamp
        ):

            issues.append({
                "field": "timestamp",
                "value": timestamp,
                "reason": "not_chronological"
            })

        if timestamp is not None:

            previous_timestamp = timestamp

        if issues:

            invalid_candles.append({
                "timestamp": timestamp,
                "datetime_utc": datetime_utc,
                "issues": issues,
            })

        else:

            candles.append(candle)

    return candles, invalid_candles


# ============================================================
# Validate complete interval
# ============================================================

def validate_interval(
    candles,
    invalid_candles
):

    total_received = (
        len(candles)
        + len(invalid_candles)
    )

    if invalid_candles:

        status = "warning"
        valid = False

    else:

        status = "ok"
        valid = True

    return {
        "status": status,
        "valid": valid,
        "total_received": total_received,
        "valid_candles": len(candles),
        "invalid_candles": len(invalid_candles),
        "issues": invalid_candles,
    }


# ============================================================
# Fetch one market
# ============================================================

def fetch_market(
    market_key,
    market_config
):

    symbol = market_config["symbol"]
    name = market_config["name"]

    print()
    print("=" * 60)
    print(f"MARKET: {name}")
    print(f"SYMBOL: {symbol}")
    print("=" * 60)

    output = {
        "data_gateway_version": "2.0",
        "symbol": symbol,
        "name": name,
        "source": "Yahoo Finance",
        "fetched_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "intervals": {},
    }

    for interval_name, interval_config in INTERVALS.items():

        interval = interval_config["interval"]
        requested_range = interval_config["range"]

        print()
        print(
            f"Yahoo Finance: "
            f"{symbol} / {interval} "
            f"(requested range: {requested_range})"
        )

        data = fetch_yahoo_data(
            symbol,
            interval,
            requested_range
        )

        candles, invalid_candles = extract_candles(
            data
        )

        validation = validate_interval(
            candles,
            invalid_candles
        )

        output["intervals"][interval_name] = {
            "interval": interval,
            "requested_range": requested_range,
            "count": len(candles),
            "candles": candles,
            "validation": validation,
        }

        print(
            f"{interval}: "
            f"{len(candles)} gültige Kerzen"
        )

        if invalid_candles:

            print(
                f"{interval}: "
                f"WARNUNG - "
                f"{len(invalid_candles)} "
                f"ungültige Kerze(n)"
            )

        else:

            print(
                f"{interval}: "
                f"Validierung OK"
            )

    output_path = (
        Path("data")
        / f"{market_key}.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(
        f"{name}: Daten erfolgreich geschrieben:"
    )
    print(output_path)

    return output_path


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)
    print("DataGW V2 - Yahoo Finance Data Fetcher")
    print("=" * 60)

    print(
        f"Märkte: {len(MARKETS)}"
    )

    print(
        "Intervalle:"
    )

    for interval_name, interval_config in INTERVALS.items():

        print(
            f"  {interval_name}: "
            f"range={interval_config['range']}"
        )

    print("=" * 60)

    successful = []
    failed = []

    for market_key, market_config in MARKETS.items():

        try:

            output_path = fetch_market(
                market_key,
                market_config
            )

            successful.append(
                str(output_path)
            )

        except Exception as error:

            print()
            print(
                f"FEHLER bei "
                f"{market_config['name']}:"
            )

            print(error)

            failed.append(
                market_config["name"]
            )

    print()
    print("=" * 60)
    print("DataGW V2 - Zusammenfassung")
    print("=" * 60)

    print(
        f"Erfolgreich: "
        f"{len(successful)} / {len(MARKETS)}"
    )

    if failed:

        print(
            f"Fehler: "
            f"{', '.join(failed)}"
        )

    else:

        print(
            "Alle Märkte erfolgreich aktualisiert."
        )

    print("=" * 60)

    if failed:

        raise RuntimeError(
            "Mindestens ein Markt konnte "
            "nicht abgerufen werden."
        )


if __name__ == "__main__":
    main()
