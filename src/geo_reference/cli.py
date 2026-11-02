from __future__ import annotations

import argparse
import json
from pathlib import Path

from .demo import create_demo
from .import_excel import import_workbook
from .parity import verify_parity, write_parity_report
from .sql_checks import run_sql_checks
from .validation import validate_database, write_report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="geo-reference", description="Import and validate geographic master data")
    commands = root.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="Build a public database from synthetic CSV fixtures")
    demo.add_argument("--output", type=Path, default=Path("data/output/demo.db"))
    demo.add_argument("--replace", action="store_true")

    import_excel = commands.add_parser("import-excel", help="Import the private full Excel workbook into SQLite")
    import_excel.add_argument("--input", type=Path, required=True)
    import_excel.add_argument("--output", type=Path, required=True)
    import_excel.add_argument("--replace", action="store_true")

    validate = commands.add_parser("validate", help="Run structural, relational and historical checks")
    validate.add_argument("--database", type=Path, required=True)
    validate.add_argument("--json", type=Path)
    validate.add_argument("--markdown", type=Path)

    parity = commands.add_parser("verify-parity", help="Independently compare an Excel workbook with an imported SQLite database")
    parity.add_argument("--input", type=Path, required=True)
    parity.add_argument("--database", type=Path, required=True)
    parity.add_argument("--json", type=Path)
    parity.add_argument("--markdown", type=Path)

    sql_checks = commands.add_parser("sql-checks", help="Run every SQL integrity query")
    sql_checks.add_argument("--database", type=Path, required=True)
    sql_checks.add_argument("--json", type=Path)
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            result = create_demo(args.output, replace=args.replace)
            unexpected = [case for case in result["cases"] if case["status"] != case["expected"]]
            result["unexpected_cases"] = unexpected
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if unexpected else 0
        if args.command == "import-excel":
            print(json.dumps(import_workbook(args.input, args.output, replace=args.replace), ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate":
            report = validate_database(args.database)
            if args.json or args.markdown:
                json_path = args.json or args.database.with_suffix(".validation.json")
                markdown_path = args.markdown or args.database.with_suffix(".validation.md")
                write_report(report, json_path, markdown_path)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["verdict"] == "PASS" else 1
        if args.command == "verify-parity":
            report = verify_parity(args.input, args.database)
            json_path = args.json or args.database.with_suffix(".parity.json")
            markdown_path = args.markdown or args.database.with_suffix(".parity.md")
            write_parity_report(report, json_path, markdown_path)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["verdict"] == "PASS" else 1
        if args.command == "sql-checks":
            report = run_sql_checks(args.database)
            if args.json:
                args.json.parent.mkdir(parents=True, exist_ok=True)
                args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["verdict"] == "PASS" else 1
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

