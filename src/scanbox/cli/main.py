from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scanbox import __version__
from scanbox.config.loader import load_app_config
from scanbox.core.enums import VerdictStatus
from scanbox.core.errors import ConfigError, InputError, ScanBoxError
from scanbox.core.models import QuarantineMode
from scanbox.pipeline.orchestrator import ScanOrchestrator
from scanbox.reporting.json_report import build_error_report, emit_report


EXIT_CODES: dict[str, int] = {
    VerdictStatus.CLEAN_BY_KNOWN_CHECKS.value: 0,
    VerdictStatus.KNOWN_MALICIOUS.value: 1,
    VerdictStatus.SUSPICIOUS.value: 2,
    VerdictStatus.PARTIAL_SCAN.value: 3,
    VerdictStatus.ENGINE_MISSING.value: 4,
    VerdictStatus.ENGINE_UNAVAILABLE.value: 5,
    VerdictStatus.SCAN_ERROR.value: 6,
    "config_error": 7,
    "input_error": 8,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scanbox", description="Scan a single local file and emit a unified JSON report.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a single file target.")
    scan_parser.add_argument("file_path", help="Path to the file to scan.")
    scan_parser.add_argument("--config", default="config/scanbox.toml", help="Path to the ScanBox TOML config.")
    scan_parser.add_argument(
        "--profile",
        choices=["conservative", "balanced", "aggressive"],
        help="Override the configured scan profile for this run.",
    )
    scan_parser.add_argument("--report-out", help="Optional file path to write the JSON report.")
    scan_parser.add_argument(
        "--quarantine",
        choices=[mode.value for mode in QuarantineMode],
        default=QuarantineMode.ASK.value,
        help="Quarantine mode for eligible known-malicious results.",
    )
    scan_parser.add_argument(
        "--dry-run-quarantine",
        action="store_true",
        help="Plan the quarantine move but do not change the file system.",
    )
    scan_parser.add_argument("--verbose", action="store_true", help="Enable verbose diagnostics on stderr.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_app_config(
            config_path=Path(args.config),
            profile_override=args.profile,
            verbose_override=args.verbose,
        )
        orchestrator = ScanOrchestrator(config)
        report = orchestrator.scan_file(
            file_path=Path(args.file_path),
            quarantine_mode=QuarantineMode(args.quarantine),
            dry_run_quarantine=args.dry_run_quarantine,
        )
        emit_report(report, report_out=Path(args.report_out) if args.report_out else None)
        return EXIT_CODES.get(report.overall_status.value, 6)
    except ConfigError as exc:
        report = build_error_report(
            original_path=str(getattr(args, "file_path", "")),
            error_code="config_error",
            error_message=str(exc),
            scanbox_version=__version__,
        )
        emit_report(report, report_out=Path(args.report_out) if getattr(args, "report_out", None) else None)
        return EXIT_CODES["config_error"]
    except InputError as exc:
        report = build_error_report(
            original_path=str(getattr(args, "file_path", "")),
            error_code="input_error",
            error_message=str(exc),
            scanbox_version=__version__,
        )
        emit_report(report, report_out=Path(args.report_out) if getattr(args, "report_out", None) else None)
        return EXIT_CODES["input_error"]
    except ScanBoxError as exc:
        report = build_error_report(
            original_path=str(getattr(args, "file_path", "")),
            error_code="scan_error",
            error_message=str(exc),
            scanbox_version=__version__,
        )
        emit_report(report, report_out=Path(args.report_out) if getattr(args, "report_out", None) else None)
        return EXIT_CODES[VerdictStatus.SCAN_ERROR.value]
    except Exception as exc:  # noqa: BLE001
        report = build_error_report(
            original_path=str(getattr(args, "file_path", "")),
            error_code="internal_error",
            error_message=str(exc),
            scanbox_version=__version__,
        )
        emit_report(report, report_out=Path(args.report_out) if getattr(args, "report_out", None) else None)
        return EXIT_CODES[VerdictStatus.SCAN_ERROR.value]


def entrypoint() -> None:
    raise SystemExit(main())
