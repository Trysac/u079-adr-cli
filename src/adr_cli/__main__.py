"""Command-line interface: ``python -m adr_cli``."""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
from pathlib import Path

from adr_cli._core import AdrError, AdrRepository

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

EXIT_OK = 0
EXIT_DOMAIN = 1
EXIT_USAGE = 2
_IO_CODES = frozenset({"format", "too_large", "write_failed"})
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _today() -> datetime.date:
    return datetime.date.today()


def _date_arg(value: str) -> datetime.date:
    if _DATE_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("not a real calendar date") from None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adr", description="Manage decision records.")
    parser.add_argument("--dir", default="doc/adr", help="ADR directory (default: doc/adr)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create the ADR directory")
    new = commands.add_parser("new", help="create an ADR")
    new.add_argument("title")
    new.add_argument("--status", default="Proposed")
    new.add_argument("--date", type=_date_arg, default=None)
    listing = commands.add_parser("list", help="list ADRs")
    listing.add_argument("--format", choices=["text", "json"], default="text")
    status = commands.add_parser("status", help="set the status of an ADR")
    status.add_argument("number", type=int)
    status.add_argument("status")
    supersede = commands.add_parser("supersede", help="supersede an ADR")
    supersede.add_argument("number", type=int)
    supersede.add_argument("title")
    supersede.add_argument("--date", type=_date_arg, default=None)
    link = commands.add_parser("link", help="link two ADRs")
    link.add_argument("source", type=int)
    link.add_argument("target", type=int)
    link.add_argument("--relation", required=True)
    commands.add_parser("index", help="print a Markdown index")
    return parser


def _print_list(repo: AdrRepository, output_format: str) -> None:
    adrs = repo.list()
    if output_format == "json":
        payload = [
            {
                "number": item.number,
                "title": item.title,
                "status": item.status,
                "date": item.date.isoformat(),
                "path": str(item.path),
            }
            for item in adrs
        ]
        print(json.dumps(payload))
    else:
        for item in adrs:
            print(f"{item.number:>4}  {item.status:<10}  {item.date.isoformat()}  {item.title}")


def _run(args: argparse.Namespace, repo: AdrRepository) -> int:
    command = args.command
    logger.debug("running command %s", command)
    if command == "init":
        repo.root.mkdir(parents=True, exist_ok=True)
        print(f"initialized {repo.root}")
    elif command == "new":
        day = args.date or _today()
        print(repo.create(args.title, today=day, status=args.status).path)
    elif command == "list":
        _print_list(repo, args.format)
    elif command == "status":
        print(repo.set_status(args.number, args.status).path)
    elif command == "supersede":
        day = args.date or _today()
        print(repo.supersede(args.number, args.title, today=day).path)
    elif command == "link":
        repo.link(args.source, args.target, args.relation)
        print(f"linked {args.source} -> {args.target}")
    else:
        sys.stdout.write(repo.render_index())
    return EXIT_OK


def _report(exc: AdrError) -> None:
    where = ""
    if exc.path is not None:
        where = f" [{exc.path}"
        if exc.line is not None:
            where += f":{exc.line}"
        where += "]"
    print(f"adr: error ({exc.code}): {exc}{where}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; return 0 on success, 1 on a domain failure, 2 on usage, I/O or parse errors."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code is None:
            return EXIT_OK
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    repo = AdrRepository(Path(args.dir))
    try:
        return _run(args, repo)
    except AdrError as exc:
        _report(exc)
        return EXIT_USAGE if exc.code in _IO_CODES else EXIT_DOMAIN
    except OSError as exc:
        print(f"adr: I/O error: {type(exc).__name__}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
