import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# DataGW V2 - Yahoo History Capability Test V1
# ============================================================

MARKETS = {
    "gold": {
        "name": "Gold",
        "symbol": "GC=F",
    },
    "silver": {
        "name": "Silver",
        "symbol": "SI=F",
    },
    "brent": {
        "name": "Brent",
        "symbol": "BZ=F",
    },
    "dax": {
        "name": "DAX",
        "symbol": "^GDAXI",
    },
    "sp500": {
        "name": "S&P 500",
        "symbol": "^GSPC",
    },
    "nasdaq100": {
        "name": "Nasdaq 100",
        "symbol": "^NDX",
    },
    "dowjones": {
        "name": "Dow Jones",
        "symbol": "^DJI",
    },
}


INTERVALS = {
    "1d": "2y",
    "1wk": "5y",
    "1mo": "max",
}


def fetch_yahoo(symbol, interval, range_value):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}"
        f"?range={range_value}"
        f"&interval={interval}"
        "&events=history"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return payload


def analyse_result(payload):
    chart = payload.get("chart", {})

    if chart.get("error"):
        return {
            "status": "ERROR",
            "error": chart["error"],
        }

    results = chart.get("result")

    if not results:
        return {
            "status": "ERROR",
            "error": "Yahoo returned no result.",
        }

    result = results[0]

    timestamps = result.get("timestamp", [])
    quote = (
        result.get("indicators", {})
        .get("quote", [{}])[0]
    )

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])

    total = len(timestamps)

    invalid = 0
    valid = 0

    for i in range(total):
        try:
            values = [
                opens[i],
                highs[i],
                lows[i],
                closes[i],
            ]

            if all(
                isinstance(value, (int, float))
                for value in values
            ):
                valid += 1
            else:
                invalid += 1

        except (IndexError, TypeError):
            invalid += 1

    first_timestamp = None
    last_timestamp = None

    if timestamps:
        first_timestamp = datetime.fromtimestamp(
            timestamps[0],
            tz=timezone.utc,
        ).isoformat()

        last_timestamp = datetime.fromtimestamp(
            timestamps[-1],
            tz=timezone.utc,
        ).isoformat()

    return {
        "status": "OK",
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
    }


def main():
    print("=" * 70)
    print("DataGW V2 - Yahoo History Capability Test V1")
    print("=" * 70)

    print()
    print("Zweck:")
    print(
        "Ermittlung der tatsächlich verfügbaren Yahoo-Historie."
    )
    print()

    errors = []
    total_tests = 0
    successful_tests = 0

    for market_key, market in MARKETS.items():

        print("-" * 70)
        print(
            f"MARKET: {market['name']} "
            f"({market['symbol']})"
        )
        print("-" * 70)

        for interval, range_value in INTERVALS.items():

            total_tests += 1

            print()
            print(
                f"Yahoo: {market['symbol']} / "
                f"{interval} / requested range: {range_value}"
            )

            try:
                payload = fetch_yahoo(
                    market["symbol"],
                    interval,
                    range_value,
                )

                result = analyse_result(payload)

                if result["status"] != "OK":
                    errors.append(
                        f"{market_key} {interval}: "
                        f"{result.get('error')}"
                    )

                    print(
                        f"STATUS: ERROR"
                    )
                    print(
                        f"Fehler: {result.get('error')}"
                    )
                    continue

                successful_tests += 1

                print(
                    f"Kerzen gesamt: "
                    f"{result['total']}"
                )

                print(
                    f"OHLC gültig:   "
                    f"{result['valid']}"
                )

                print(
                    f"OHLC ungültig: "
                    f"{result['invalid']}"
                )

                print(
                    f"Erste Kerze:   "
                    f"{result['first_timestamp']}"
                )

                print(
                    f"Letzte Kerze:  "
                    f"{result['last_timestamp']}"
                )

                if result["invalid"] == 0:
                    print("STATUS: PASS")
                else:
                    print("STATUS: WARNUNG")

            except Exception as exc:
                errors.append(
                    f"{market_key} {interval}: {exc}"
                )

                print(
                    f"STATUS: ERROR"
                )
                print(
                    f"Fehler: {exc}"
                )

        print()

    print("=" * 70)
    print("HISTORY CAPABILITY SUMMARY")
    print("=" * 70)

    print(
        f"Tests erfolgreich: "
        f"{successful_tests}/{total_tests}"
    )

    print(
        f"Fehler: "
        f"{len(errors)}"
    )

    if errors:
        print()
        print("FEHLERDETAILS:")

        for error in errors:
            print(f"  - {error}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
