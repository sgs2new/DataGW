import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# DataGW - Yahoo Finance Market Data Fetcher
# ============================================================

RANGE = "1y"

INTERVALS = {
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
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

def fetch_yahoo_data(symbol, interval):
    url = (
        "https://query2.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval={interval}&range={RANGE}"
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
# Extract OHLC candles
# ============================================================

def extract_candles(data):
    result = data["chart"]["result"][0]

    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    candles = []

    for i, timestamp in enumerate(timestamps):

        open_price = quote["open"][i]
        high_price = quote["high"][i]
        low_price = quote["low"][i]
        close_price = quote["close"][i]

        if None in (
            open_price,
            high_price,
            low_price,
            close_price,
        ):
            continue

        candles.append(
            {
                "timestamp": timestamp,
                "datetime_utc": datetime.fromtimestamp(
                    timestamp,
                    tz=timezone.utc
                ).isoformat(),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
            }
        )

    return candles


# ============================================================
# Fetch one market
# ============================================================

def fetch_market(market_key, market_config):

    symbol = market_config["symbol"]
    name = market_config["name"]

    print()
    print("=" * 60)
    print(f"MARKET: {name}")
    print(f"SYMBOL: {symbol}")
    print("=" * 60)

    output = {
        "symbol": symbol,
        "name": name,
        "source": "Yahoo Finance",
        "fetched_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "intervals": {},
    }

    for interval_name, interval in INTERVALS.items():

        print(
            f"Yahoo Finance: "
            f"{symbol} / {interval}"
        )

        data = fetch_yahoo_data(
            symbol,
            interval
        )

        candles = extract_candles(data)

        output["intervals"][interval_name] = {
            "interval": interval,
            "range": RANGE,
            "count": len(candles),
            "candles": candles,
        }

        print(
            f"{interval}: "
            f"{len(candles)} Kerzen abgerufen"
        )

    output_path = (
        Path("data") /
        f"{market_key}.json"
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
    print("DataGW - Yahoo Finance Data Fetcher")
    print("=" * 60)
    print(
        f"Märkte: {len(MARKETS)}"
    )
    print(
        f"Intervalle: {', '.join(INTERVALS.keys())}"
    )
    print(
        f"Historie: {RANGE}"
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
    print("DataGW - Zusammenfassung")
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
