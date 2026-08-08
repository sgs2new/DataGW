import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SYMBOL = "GC=F"
INTERVAL = "1d"
RANGE = "5d"

URL = (
    f"https://query2.finance.yahoo.com/v8/finance/chart/"
    f"{SYMBOL}?interval={INTERVAL}&range={RANGE}"
)


def fetch_yahoo_data():
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    data = fetch_yahoo_data()

    result = data["chart"]["result"][0]
    meta = result["meta"]

    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    # Letzte vorhandene vollständige OHLC-Kerze suchen
    candle = None

    for i in range(len(timestamps) - 1, -1, -1):
        values = {
            "timestamp": timestamps[i],
            "open": quote["open"][i],
            "high": quote["high"][i],
            "low": quote["low"][i],
            "close": quote["close"][i],
        }

        if all(value is not None for value in values.values()):
            candle = values
            break

    if candle is None:
        raise RuntimeError("Keine vollständige OHLC-Kerze gefunden.")

    timestamp = candle["timestamp"]

    output = {
        "symbol": meta.get("symbol", SYMBOL),
        "interval": INTERVAL,
        "timestamp": timestamp,
        "datetime_utc": datetime.fromtimestamp(
            timestamp, tz=timezone.utc
        ).isoformat(),
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "source": "Yahoo Finance",
        "source_endpoint": URL,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path("data/gold.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print("Gold-Daten erfolgreich geschrieben:")
    print(output_path)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
