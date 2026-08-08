import json
import math
from datetime import datetime, timezone
from pathlib import Path

# ============================================================
# DataGW V2 - Consumer Test V1.1
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


# ============================================================
# LOAD
# ============================================================

def load_market(market):
    path = DATA_DIR / f"{market}.json"

    if not path.exists():
        raise FileNotFoundError(
            f"Datei fehlt: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# METADATA
# ============================================================

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


# ============================================================
# BASIC CANDLE VALIDATION
# ============================================================

def validate_candle_structure(candle):
    """
    Prüft:
    - alle benötigten Felder vorhanden
    - OHLC numerisch
    - OHLC endlich
    - Timestamp Integer
    - datetime_utc String
    """

    errors = []

    if not isinstance(candle, dict):
        return ["Kerze ist kein Objekt"]

    for field in REQUIRED_OHLC_FIELDS:
        if field not in candle:
            errors.append(
                f"Feld fehlt: {field}"
            )

    if errors:
        return errors

    # --------------------------------------------------------
    # OHLC
    # --------------------------------------------------------

    for field in ["open", "high", "low", "close"]:
        value = candle[field]

        # bool explizit ausschließen, da bool in Python
        # technisch von int erbt.
        if isinstance(value, bool):
            errors.append(
                f"{field} ist bool statt Zahl"
            )
            continue

        if not isinstance(value, (int, float)):
            errors.append(
                f"{field} ist nicht numerisch"
            )
            continue

        if not math.isfinite(float(value)):
            errors.append(
                f"{field} ist nicht endlich"
            )

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    timestamp = candle["timestamp"]

    if isinstance(timestamp, bool):
        errors.append(
            "timestamp ist bool statt Integer"
        )
    elif not isinstance(timestamp, int):
        errors.append(
            "timestamp ist kein Integer"
        )
    elif timestamp <= 0:
        errors.append(
            "timestamp ist <= 0"
        )

    # --------------------------------------------------------
    # DATETIME UTC
    # --------------------------------------------------------

    datetime_utc = candle["datetime_utc"]

    if not isinstance(datetime_utc, str):
        errors.append(
            "datetime_utc ist kein String"
        )

    return errors


# ============================================================
# OHLC LOGIC
# ============================================================

def validate_ohlc_logic(candle):
    """
    Prüft die logischen Beziehungen einer OHLC-Kerze:

        high >= open
        high >= close
        low  <= open
        low  <= close
        high >= low
    """

    errors = []

    try:
        open_price = float(candle["open"])
        high_price = float(candle["high"])
        low_price = float(candle["low"])
        close_price = float(candle["close"])
    except (KeyError, TypeError, ValueError):
        return [
            "OHLC-Werte konnten nicht numerisch verarbeitet werden"
        ]

    if high_price < open_price:
        errors.append(
            f"High ({high_price}) < Open ({open_price})"
        )

    if high_price < close_price:
        errors.append(
            f"High ({high_price}) < Close ({close_price})"
        )

    if low_price > open_price:
        errors.append(
            f"Low ({low_price}) > Open ({open_price})"
        )

    if low_price > close_price:
        errors.append(
            f"Low ({low_price}) > Close ({close_price})"
        )

    if high_price < low_price:
        errors.append(
            f"High ({high_price}) < Low ({low_price})"
        )

    return errors


# ============================================================
# TIMESTAMP / DATETIME VALIDATION
# ============================================================

def validate_datetime(candle):
    """
    Prüft:
    - datetime_utc ist gültiges ISO-Format
    - Zeitzone ist UTC
    - Timestamp und datetime_utc stimmen überein
    """

    errors = []

    timestamp = candle.get("timestamp")
    datetime_utc = candle.get("datetime_utc")

    if not isinstance(timestamp, int):
        return ["Timestamp nicht prüfbar"]

    if not isinstance(datetime_utc, str):
        return ["datetime_utc nicht prüfbar"]

    # --------------------------------------------------------
    # ISO-8601 / UTC
    # --------------------------------------------------------

    normalized = datetime_utc.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return [
            f"Ungültiges datetime_utc: {datetime_utc!r}"
        ]

    if parsed.tzinfo is None:
        errors.append(
            "datetime_utc enthält keine Zeitzone"
        )
    else:
        utc_offset = parsed.utcoffset()

        if utc_offset != timezone.utc.utcoffset(parsed):
            errors.append(
                "datetime_utc ist nicht UTC"
            )

    # --------------------------------------------------------
    # Timestamp ↔ datetime_utc
    # --------------------------------------------------------

    if parsed.tzinfo is not None:
        parsed_timestamp = int(
            parsed.timestamp()
        )

        if parsed_timestamp != timestamp:
            errors.append(
                "timestamp und datetime_utc stimmen nicht überein"
            )

    return errors


# ============================================================
# INTERVAL ANALYSIS
# ============================================================

def analyse_interval(interval_name, interval_data):
    candles = interval_data.get("candles", [])

    if not isinstance(candles, list):
        raise ValueError(
            "candles ist keine Liste"
        )

    total = len(candles)

    structure_valid = 0
    ohlc_valid = 0
    datetime_valid = 0

    candle_errors = []

    timestamps = []

    # --------------------------------------------------------
    # Candle-by-candle validation
    # --------------------------------------------------------

    for index, candle in enumerate(candles):

        errors = []

        # Basic structure
        structure_errors = validate_candle_structure(
            candle
        )

        if not structure_errors:
            structure_valid += 1
        else:
            errors.extend(structure_errors)

        # OHLC logic
        if not structure_errors:
            ohlc_errors = validate_ohlc_logic(
                candle
            )

            if not ohlc_errors:
                ohlc_valid += 1
            else:
                errors.extend(ohlc_errors)

        # Timestamp / datetime
        if not structure_errors:
            datetime_errors = validate_datetime(
                candle
            )

            if not datetime_errors:
                datetime_valid += 1
            else:
                errors.extend(datetime_errors)

        # Timestamp collection
        if (
            isinstance(candle, dict)
            and isinstance(candle.get("timestamp"), int)
            and not isinstance(candle.get("timestamp"), bool)
        ):
            timestamps.append(
                candle["timestamp"]
            )

        if errors:
            candle_errors.append(
                {
                    "index": index,
                    "errors": errors,
                }
            )

    # --------------------------------------------------------
    # Chronology
    # --------------------------------------------------------

    chronology_errors = []

    for index in range(1, len(timestamps)):
        previous_timestamp = timestamps[index - 1]
        current_timestamp = timestamps[index]

        if current_timestamp <= previous_timestamp:
            chronology_errors.append(
                f"Timestamp-Reihenfolge verletzt "
                f"bei Position {index}: "
                f"{previous_timestamp} -> "
                f"{current_timestamp}"
            )

    # --------------------------------------------------------
    # Duplicate timestamps
    # --------------------------------------------------------

    duplicate_timestamps = []

    seen = set()

    for timestamp in timestamps:
        if timestamp in seen:
            duplicate_timestamps.append(
                timestamp
            )
        else:
            seen.add(timestamp)

    for timestamp in duplicate_timestamps:
        chronology_errors.append(
            f"Doppelter Timestamp: {timestamp}"
        )

    # --------------------------------------------------------
    # Quality
    # --------------------------------------------------------

    if total == 0:
        quality = 0.0
    else:
        quality = (
            structure_valid / total
        ) * 100

    # --------------------------------------------------------
    # Last close
    # --------------------------------------------------------

    last_close = None

    if candles:
        valid_timestamp_candles = [
            candle
            for candle in candles
            if (
                isinstance(candle, dict)
                and isinstance(candle.get("timestamp"), int)
                and not isinstance(candle.get("timestamp"), bool)
            )
        ]

        if valid_timestamp_candles:
            latest_candle = max(
                valid_timestamp_candles,
                key=lambda candle: candle["timestamp"]
            )

            last_close = latest_candle.get(
                "close"
            )

    # --------------------------------------------------------
    # Overall interval status
    # --------------------------------------------------------

    status = (
        structure_valid == total
        and ohlc_valid == total
        and datetime_valid == total
        and not chronology_errors
    )

    return {
        "interval": interval_name,
        "total": total,
        "structure_valid": structure_valid,
        "ohlc_valid": ohlc_valid,
        "datetime_valid": datetime_valid,
        "quality": quality,
        "chronology_errors": chronology_errors,
        "candle_errors": candle_errors,
        "last_close": last_close,
        "status": status,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("DataGW V2 - Consumer Test V1.1")
    print("=" * 60)

    print(f"Märkte: {len(MARKETS)}")
    print(
        f"Intervalle: {', '.join(REQUIRED_INTERVALS)}"
    )
    print()

    total_markets = 0
    total_intervals = 0
    failed_intervals = 0
    errors = []

    # --------------------------------------------------------
    # Markets
    # --------------------------------------------------------

    for market in MARKETS:

        print("-" * 60)
        print(f"MARKET: {market.upper()}")
        print("-" * 60)

        market_ok = True

        try:
            data = load_market(market)

            validate_version(data)
            validate_metadata(data)

            intervals = data["intervals"]

            # ------------------------------------------------
            # Intervals
            # ------------------------------------------------

            for interval in REQUIRED_INTERVALS:

                total_intervals += 1

                if interval not in intervals:
                    failed_intervals += 1
                    market_ok = False

                    error = (
                        f"{market}/{interval}: "
                        f"Intervall fehlt"
                    )

                    errors.append(error)

                    print(
                        f"  {interval:<4} "
                        f"STATUS: FAIL"
                    )

                    print(
                        f"       Fehler: "
                        f"Intervall fehlt"
                    )

                    continue

                result = analyse_interval(
                    interval,
                    intervals[interval]
                )

                total = result["total"]
                quality = result["quality"]

                if result["status"]:
                    status = "PASS"
                else:
                    status = "FAIL"
                    failed_intervals += 1
                    market_ok = False

                # --------------------------------------------
                # Summary line
                # --------------------------------------------

                print(
                    f"  {interval:<4} "
                    f"{result['structure_valid']:>4}/"
                    f"{total:<4} Kerzen "
                    f"| {quality:>6.2f}% "
                    f"| {status}"
                )

                # --------------------------------------------
                # Detailed validation
                # --------------------------------------------

                print(
                    f"       OHLC:       "
                    f"{result['ohlc_valid']}/{total}"
                )

                print(
                    f"       Timestamp:  "
                    f"{result['datetime_valid']}/{total}"
                )

                if result["chronology_errors"]:
                    print(
                        f"       Chronologie: FAIL"
                    )
                else:
                    print(
                        f"       Chronologie: OK"
                    )

                if result["last_close"] is not None:
                    print(
                        f"       letzter Close: "
                        f"{result['last_close']}"
                    )

                # --------------------------------------------
                # Error details
                # --------------------------------------------

                if result["candle_errors"]:
                    print(
                        "       Kerzenfehler:"
                    )

                    # Maximal 10 Fehler pro Intervall
                    # ausgeben, damit der Workflow-Log
                    # nicht unnötig groß wird.
                    for candle_error in result[
                        "candle_errors"
                    ][:10]:

                        print(
                            f"         - Kerze "
                            f"{candle_error['index']}: "
                            f"{'; '.join(candle_error['errors'])}"
                        )

                    remaining = (
                        len(result["candle_errors"]) - 10
                    )

                    if remaining > 0:
                        print(
                            f"         ... "
                            f"{remaining} weitere Fehler"
                        )

                if result["chronology_errors"]:
                    print(
                        "       Chronologiefehler:"
                    )

                    for error in result[
                        "chronology_errors"
                    ][:10]:

                        print(
                            f"         - {error}"
                        )

                    remaining = (
                        len(result["chronology_errors"]) - 10
                    )

                    if remaining > 0:
                        print(
                            f"         ... "
                            f"{remaining} weitere Fehler"
                        )

                print()

            if market_ok:
                total_markets += 1

        except Exception as exc:

            errors.append(
                f"{market}: {exc}"
            )

            market_ok = False

            print(
                f"FEHLER: {exc}"
            )

            print()

    # ========================================================
    # SUMMARY
    # ========================================================

    print("=" * 60)
    print("CONSUMER TEST SUMMARY")
    print("=" * 60)

    print(
        f"Märkte erfolgreich:       "
        f"{total_markets}/{len(MARKETS)}"
    )

    print(
        f"Intervalle geprüft:       "
        f"{total_intervals}"
    )

    print(
        f"Fehlgeschlagene Intervalle: "
        f"{failed_intervals}"
    )

    print(
        f"Fehler:                   "
        f"{len(errors)}"
    )

    if errors:

        print()
        print("FEHLERDETAILS:")

        for error in errors:
            print(
                f"  - {error}"
            )

        print()
        print("STATUS: FAIL")

        raise RuntimeError(
            "DataGW V2 Consumer Test V1.1 fehlgeschlagen."
        )

    print()
    print("STATUS: PASS")
    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
