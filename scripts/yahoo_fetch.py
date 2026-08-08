import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SYMBOL = "GC=F"
NAME = "Gold"
RANGE = "1y"

INTERVALS = {
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
}


def fetch_yahoo_data(interval):
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/"
        f"{SYMBOL}?interval={interval}&range={RANGE}"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


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

        candles.append({
            "timestamp": timestamp,
            "datetime_utc": datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            ).isoformat(),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price
        })

    return candles


def main():

    output = {
        "symbol": SYMBOL,
        "name": NAME,
        "source": "Yahoo Finance",
        "fetched_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "intervals": {}
    }

    for name, interval in INTERVALS.items():

        print(f"Yahoo Finance: {SYMBOL} / {interval}")

        data = fetch_yahoo_data(interval)
        candles = extract_candles(data)

        output["intervals"][name] = {
            "interval": interval,
            "range": RANGE,
            "count": len(candles),
            "candles": candles
        }

        print(
            f"{interval}: {len(candles)} Kerzen abgerufen"
        )

    output_path = Path("data/gold.json")
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
    print("Gold-Daten erfolgreich geschrieben:")
    print(output_path)


if __name__ == "__main__":
    main()
