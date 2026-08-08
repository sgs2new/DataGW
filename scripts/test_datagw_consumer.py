import json
from pathlib import Path


# ============================================================
# DataGW V2 - Consumer Test V1
# ============================================================

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MARKETS = [
    "gold",
    "silver",
    "brent",
    "dax",
    "sp500",
    "nasdaq100",
    "dowjones",
]

REQUIRED_INTERVALS = ["1d", "1wk", "1mo"]
REQUIRED_OHLC_FIELDS = [
    "timestamp",
    "datetime_utc",
    "open",
    "high",
    "low",
    "close",
]


def load_market(market):
    path = DATA_DIR / f"{market}.json"

    if not path.exists():
        raise FileNotFoundError(f"Datei fehlt: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_version(data):
    version = data.get("data_gateway_version")

    if version != "2.0":
        raise ValueError(
            f"Ungültige DataGW-Version: {version!r}"
        )


def validate_metadata(data):
    required_fields = [
        "symbol",
        "name",
        "source",
        "fetched_at_utc",
        "intervals",
    ]

    missing = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing:
        raise ValueError(
            f"Fehlende Metadaten: {', '.join(missing)}"
        )


def validate_candle(candle):
    for field in REQUIRED_OHLC_FIELDS:
        if field not in candle:
            return False

    for field in ["open", "high", "low", "close"]:
        if not isinstance(candle[field], (int, float)):
            return False

    if not isinstance(candle["timestamp"], int):
        return False

    if not isinstance(candle["datetime_utc"], str):
        return False

    return True


def analyse_interval(interval_data):
    candles = interval_data.get("candles", [])

    if not isinstance(candles, list):
        raise ValueError("candles ist keine Liste")

    total = len(candles)

    valid = [
        candle
        for candle in candles
        if validate_candle(candle)
    ]

    invalid_count = total - len(valid)

    if total == 0:
        quality = 0.0
    else:
        quality = (len(valid) / total) * 100

    last_close = None

    if valid:
        valid_sorted = sorted(
            valid,
            key=lambda candle: candle["timestamp"]
        )
        last_close = valid_sorted[-1]["close"]

    return {
        "total": total,
        "valid": len(valid),
        "invalid": invalid_count,
        "quality": quality,
        "last_close": last_close,
    }


def main():
    print("=" * 60)
    print("DataGW V2 - Consumer Test V1")
    print("=" * 60)

    print(f"Märkte: {len(MARKETS)}")
    print(f"Intervalle: {', '.join(REQUIRED_INTERVALS)}")
    print()

    total_markets = 0
    total_intervals = 0
    errors = []

    for market in MARKETS:
        print("-" * 60)
        print(f"MARKET: {market.upper()}")

        try:
            data = load_market(market)

            validate_version(data)
            validate_metadata(data)

            intervals = data["intervals"]

            for interval in REQUIRED_INTERVALS:
                total_intervals += 1

                if interval not in intervals:
                    raise ValueError(
                        f"Intervall fehlt: {interval}"
                    )

                result = analyse_interval(
                    intervals[interval]
                )

                quality = result["quality"]

                if quality >= 99.0:
                    status = "OK"
                else:
                    status = "WARNUNG"

                print(
                    f"  {interval:<4} "
                    f"{result['valid']:>4}/{result['total']:<4} Kerzen "
                    f"| {quality:>6.2f}% "
                    f"| {status}"
                )

                if result["last_close"] is not None:
                    print(
                        f"       letzter Close: "
                        f"{result['last_close']}"
                    )

            total_markets += 1

        except Exception as exc:
            errors.append(
                f"{market}: {exc}"
            )
            print(f"  FEHLER: {exc}")

        print()

    print("=" * 60)
    print("CONSUMER TEST SUMMARY")
    print("=" * 60)

    print(f"Märkte erfolgreich:       {total_markets}/{len(MARKETS)}")
    print(f"Intervalle geprüft:       {total_intervals}")
    print(f"Fehler:                   {len(errors)}")

    if errors:
        print()
        print("FEHLERDETAILS:")

        for error in errors:
            print(f"  - {error}")

        print()
        print("STATUS: FAIL")
        raise RuntimeError(
            "DataGW V2 Consumer Test fehlgeschlagen."
        )

    print()
    print("STATUS: PASS")
    print("=" * 60)


if __name__ == "__main__":
    main()
