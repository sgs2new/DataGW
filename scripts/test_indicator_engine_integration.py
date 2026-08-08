import json
import importlib.util
import sys
from pathlib import Path


# ============================================================
# DataGW V2 -> Trading Desk Indicator Engine V1
# Real Integration Test V2
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ENGINE_PATH = BASE_DIR / "scripts" / "trading_desk_indicator_engine.py"

MARKETS = [
    "gold",
    "silver",
    "brent",
    "dax",
    "sp500",
    "nasdaq100",
    "dowjones",
]

INTERVALS = [
    "1d",
    "1wk",
    "1mo",
]


# ============================================================
# Load Indicator Engine
# ============================================================

def load_indicator_engine():

    spec = importlib.util.spec_from_file_location(
        "trading_desk_indicator_engine",
        ENGINE_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Indicator Engine konnte nicht geladen werden."
        )

    engine = importlib.util.module_from_spec(spec)

    sys.modules[
        "trading_desk_indicator_engine"
    ] = engine

    spec.loader.exec_module(engine)

    return engine


# ============================================================
# Load DataGW market JSON
# ============================================================

def load_market(market):

    path = DATA_DIR / f"{market}.json"

    if not path.exists():
        raise FileNotFoundError(
            f"DataGW-Datei fehlt: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# Analyse indicator results
# ============================================================

def analyse_results(
    engine,
    results,
):

    counts = {
        engine.STATUS_CALCULATED: 0,
        engine.STATUS_INSUFFICIENT: 0,
        engine.STATUS_INVALID: 0,
        engine.STATUS_NOT_AVAILABLE: 0,
        engine.STATUS_ERROR: 0,
    }

    for result in results.values():

        status = result.status

        if status not in counts:
            counts[status] = 0

        counts[status] += 1

    return counts


# ============================================================
# Main integration test
# ============================================================

def main():

    engine = load_indicator_engine()

    print("=" * 96)
    print(
        "DataGW V2 -> Trading Desk Indicator Engine V1"
    )
    print(
        "REAL INTEGRATION TEST V2"
    )
    print("=" * 96)

    print()
    print(
        "DataGW Contract: DGW2-TD-IF-1.0"
    )

    print(
        f"Märkte: {len(MARKETS)}"
    )

    print(
        f"Intervalle: {', '.join(INTERVALS)}"
    )

    print(
        f"Kombinationen: "
        f"{len(MARKETS) * len(INTERVALS)}"
    )

    print()

    rows = []
    technical_errors = []

    # ========================================================
    # Process all markets and intervals
    # ========================================================

    for market in MARKETS:

        print("-" * 96)
        print(
            f"MARKET: {market.upper()}"
        )
        print("-" * 96)

        try:

            data = load_market(market)

        except Exception as error:

            technical_errors.append(
                f"{market}: {error}"
            )

            print(
                f"FEHLER beim Laden: {error}"
            )

            print()

            continue

        for interval in INTERVALS:

            try:

                candles = (
                    engine.candles_from_datagw(
                        data,
                        interval,
                    )
                )

                results = engine.calculate_all(
                    candles,
                    interval,
                )

                counts = analyse_results(
                    engine,
                    results,
                )

                row = {
                    "market": market,
                    "interval": interval,
                    "candles": len(candles),
                    "indicators": len(results),
                    "calculated": counts[
                        engine.STATUS_CALCULATED
                    ],
                    "insufficient_history": counts[
                        engine.STATUS_INSUFFICIENT
                    ],
                    "invalid_data": counts[
                        engine.STATUS_INVALID
                    ],
                    "not_available": counts[
                        engine.STATUS_NOT_AVAILABLE
                    ],
                    "error": counts[
                        engine.STATUS_ERROR
                    ],
                }

                rows.append(row)

                print(
                    f"{interval:<5} "
                    f"Kerzen: {row['candles']:>4} | "
                    f"Indikatoren: {row['indicators']:>2} | "
                    f"CALCULATED: {row['calculated']:>2} | "
                    f"HISTORY: {row['insufficient_history']:>2} | "
                    f"INVALID: {row['invalid_data']:>2} | "
                    f"N/A: {row['not_available']:>2} | "
                    f"ERROR: {row['error']:>2}"
                )

            except Exception as error:

                technical_errors.append(
                    f"{market}/{interval}: "
                    f"{type(error).__name__}: {error}"
                )

                print(
                    f"{interval:<5} "
                    f"TECHNISCHER FEHLER: {error}"
                )

        print()

    # ========================================================
    # Summary
    # ========================================================

    total_indicators = sum(
        row["indicators"]
        for row in rows
    )

    total_calculated = sum(
        row["calculated"]
        for row in rows
    )

    total_insufficient = sum(
        row["insufficient_history"]
        for row in rows
    )

    total_invalid = sum(
        row["invalid_data"]
        for row in rows
    )

    total_not_available = sum(
        row["not_available"]
        for row in rows
    )

    total_error = sum(
        row["error"]
        for row in rows
    )

    expected_combinations = (
        len(MARKETS) * len(INTERVALS)
    )

    processed_combinations = len(rows)

    # ========================================================
    # Acceptance criteria
    # ========================================================

    status = "PASS"

    if processed_combinations != expected_combinations:
        status = "FAIL"

    if technical_errors:
        status = "FAIL"

    if total_error > 0:
        status = "FAIL"

    # ========================================================
    # Print summary
    # ========================================================

    print("=" * 96)
    print(
        "INDICATOR ENGINE INTEGRATION SUMMARY"
    )
    print("=" * 96)

    print(
        f"Kombinationen verarbeitet: "
        f"{processed_combinations}/{expected_combinations}"
    )

    print(
        f"Indikatorberechnungen: "
        f"{total_indicators}"
    )

    print(
        f"CALCULATED: "
        f"{total_calculated}"
    )

    print(
        f"INSUFFICIENT_HISTORY: "
        f"{total_insufficient}"
    )

    print(
        f"INVALID_DATA: "
        f"{total_invalid}"
    )

    print(
        f"NOT_AVAILABLE: "
        f"{total_not_available}"
    )

    print(
        f"ERROR: "
        f"{total_error}"
    )

    print(
        f"Technische Fehler: "
        f"{len(technical_errors)}"
    )

    # ========================================================
    # Technical errors
    # ========================================================

    if technical_errors:

        print()
        print(
            "TECHNISCHE FEHLER:"
        )

        for error in technical_errors:

            print(
                f"  - {error}"
            )

    # ========================================================
    # Final status
    # ========================================================

    print()
    print(
        f"STATUS: {status}"
    )

    print("=" * 96)

    # ========================================================
    # Machine-readable report
    # ========================================================

    report = {
        "test": (
            "DataGW V2 -> "
            "Trading Desk Indicator Engine V1"
        ),
        "test_version": "2.0",
        "contract": "DGW2-TD-IF-1.0",
        "markets": MARKETS,
        "intervals": INTERVALS,
        "expected_combinations": expected_combinations,
        "processed_combinations": processed_combinations,
        "summary": {
            "indicators": total_indicators,
            "calculated": total_calculated,
            "insufficient_history": total_insufficient,
            "invalid_data": total_invalid,
            "not_available": total_not_available,
            "error": total_error,
            "technical_errors": len(
                technical_errors
            ),
            "status": status,
        },
        "rows": rows,
        "technical_errors": technical_errors,
    }

    report_path = (
        BASE_DIR
        / "DataGW_V2_Indicator_Engine_Integration_Test_Report.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        f"Report gespeichert:"
    )
    print(report_path)

    # ========================================================
    # Fail GitHub Actions on technical failure
    # ========================================================

    if status != "PASS":

        raise RuntimeError(
            "DataGW V2 Indicator Engine "
            "Integration Test fehlgeschlagen."
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
