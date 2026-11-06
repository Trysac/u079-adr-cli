"""Tests for the adr_cli public API and command line."""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

import adr_cli
import adr_cli.__main__ as cli
import adr_cli._core as core
from adr_cli import Adr, AdrError, AdrRepository, Link, parse_adr

TODAY = date(2026, 11, 5)
KEYS = {"number", "title", "status", "date", "path"}


def adr_text(
    number: int,
    title: str,
    status: str = "Accepted",
    extra: str = "",
    eol: str = "\n",
) -> str:
    text = (
        f"# {number}. {title}\n\nDate: 2026-01-02\n\n## Status\n\n{status}\n{extra}\n"
        "## Context\n\nSome context.\n\n## Decision\n\nDo it.\n\n## Consequences\n\nNone.\n"
    )
    return text.replace("\n", eol)


def put(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_bytes(text.encode("utf-8"))
    return path


def seed(directory: Path, eol: str = "\n") -> None:
    put(directory, "0001-first.md", adr_text(1, "First"))
    put(directory, "0002-old-title.md", adr_text(2, "Old title", eol=eol))
    put(directory, "0003-third.md", adr_text(3, "Third"))


def caught(call: Callable[[], object]) -> AdrError:
    try:
        call()
    except AdrError as exc:
        return exc
    raise AssertionError("AdrError was not raised")


def test_public_api_and_immutability() -> None:
    expected = {"Adr", "AdrError", "AdrRepository", "Link", "__version__", "parse_adr"}
    assert set(adr_cli.__all__) == expected
    link = Link("Amends", 1)
    with pytest.raises(FrozenInstanceError):
        link.target = 2


def test_logger_has_only_a_null_handler() -> None:
    handlers = logging.getLogger("adr_cli._core").handlers
    assert handlers
    assert all(isinstance(handler, logging.NullHandler) for handler in handlers)


def test_cli_new_writes_exact_bytes(tmp_path: Path) -> None:
    code = cli.main(["--dir", str(tmp_path), "new", "Use Postgres", "--date", "2026-11-05"])
    assert code == 0
    expected = (
        b"# 1. Use Postgres\n\nDate: 2026-11-05\n\n## Status\n\nProposed\n\n"
        b"## Context\n\nTODO\n\n## Decision\n\nTODO\n\n## Consequences\n\nTODO\n"
    )
    assert (tmp_path / "0001-use-postgres.md").read_bytes() == expected


def test_next_number_ignores_foreign_names(tmp_path: Path) -> None:
    put(tmp_path, "0001-a.md", adr_text(1, "A"))
    put(tmp_path, "0003-c.md", adr_text(3, "C"))
    for name in ("0002-b.md.bak", "00002-b.md", "0002-B.md", "notes.md"):
        put(tmp_path, name, "garbage")
    repo = AdrRepository(tmp_path)
    assert [item.number for item in repo.list()] == [1, 3]
    created = repo.create("Next", today=TODAY)
    assert created.number == 4
    assert created.path.name == "0004-next.md"


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_supersede_rewrites_only_the_status_section(tmp_path: Path, eol: str) -> None:
    seed(tmp_path, eol)
    repo = AdrRepository(tmp_path)
    new = repo.supersede(2, "New title", today=TODAY)
    assert new.path.name == "0004-new-title.md"
    assert new.links == (Link("Supersedes", 2),)
    new_text = new.path.read_text(encoding="utf-8")
    assert "\nSupersedes [2. Old title](0002-old-title.md)\n" in new_text
    assert "Date: 2026-11-05" in new_text
    status = "Superseded by [4. New title](0004-new-title.md)"
    expected = adr_text(2, "Old title", status=status, eol=eol).encode("utf-8")
    assert (tmp_path / "0002-old-title.md").read_bytes() == expected
    old = repo.get(2)
    assert old.status == "Superseded"
    assert old.links == (Link("Superseded by", 4),)


def test_superseded_adr_is_terminal(tmp_path: Path) -> None:
    seed(tmp_path)
    repo = AdrRepository(tmp_path)
    repo.supersede(2, "New title", today=TODAY)
    path = tmp_path / "0002-old-title.md"
    before = path.read_bytes()
    names = sorted(os.listdir(tmp_path))
    attempts = [
        lambda: repo.set_status(2, "Accepted"),
        lambda: repo.supersede(2, "Again", today=TODAY),
        lambda: repo.link(2, 1, "Amends"),
    ]
    for attempt in attempts:
        assert caught(attempt).code == "already_superseded"
    assert path.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == names


def test_bare_superseded_status_is_terminal(tmp_path: Path) -> None:
    put(tmp_path, "0001-a.md", adr_text(1, "A", status="SUPERSEDED"))
    repo = AdrRepository(tmp_path)
    assert repo.get(1).status == "Superseded"
    assert caught(lambda: repo.set_status(1, "Accepted")).code == "already_superseded"


def test_list_is_sorted_and_json_has_exact_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(tmp_path, "0003-c.md", adr_text(3, "C"))
    put(tmp_path, "0001-a.md", adr_text(1, "A", status="proposed"))
    repo = AdrRepository(tmp_path)
    items = repo.list()
    assert [item.number for item in items] == [1, 3]
    assert items[0] == Adr(1, "A", "Proposed", date(2026, 1, 2), tmp_path / "0001-a.md", ())
    assert cli.main(["--dir", str(tmp_path), "list", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [set(entry) for entry in data] == [KEYS, KEYS]
    assert data[0]["date"] == "2026-01-02"
    assert data[0]["path"] == str(tmp_path / "0001-a.md")


def test_list_text_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seed(tmp_path)
    assert cli.main(["--dir", str(tmp_path), "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert "Old title" in lines[1]


def test_bad_first_line_is_a_format_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(tmp_path, "0001-title.md", adr_text(1, "Title").replace("# 1. Title", "#1. Title"))
    exc = caught(AdrRepository(tmp_path).list)
    assert exc.code == "format"
    assert exc.line == 1
    assert exc.path == tmp_path / "0001-title.md"
    assert cli.main(["--dir", str(tmp_path), "list"]) == 2
    assert "format" in capsys.readouterr().err


def test_invalid_status_lists_the_allowed_words(tmp_path: Path) -> None:
    put(tmp_path, "0001-a.md", adr_text(1, "A"))
    repo = AdrRepository(tmp_path)
    exc = caught(lambda: repo.set_status(1, "Maybe"))
    assert exc.code == "invalid_status"
    assert "Proposed, Accepted, Rejected, Deprecated" in str(exc)
    assert caught(lambda: repo.set_status(1, "Superseded")).code == "invalid_status"
    assert caught(lambda: repo.create("T", today=TODAY, status="nope")).code == "invalid_status"
    long_exc = caught(lambda: repo.set_status(1, "x" * 1000))
    assert "x" * 201 not in str(long_exc)
    assert len(str(long_exc)) < 300


def test_supersede_survives_a_failed_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed(tmp_path)
    old = tmp_path / "0002-old-title.md"
    before = old.read_bytes()

    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken_replace)
    exc = caught(lambda: AdrRepository(tmp_path).supersede(2, "New title", today=TODAY))
    assert exc.code == "write_failed"
    assert (tmp_path / "0004-new-title.md").exists()
    assert old.read_bytes() == before
    assert not [name for name in os.listdir(tmp_path) if name.startswith(".adr-")]


def test_invalid_title_literals(tmp_path: Path) -> None:
    repo = AdrRepository(tmp_path)
    for title in ("", "!!", "a\nb", "\u65e5\u672c"):
        assert caught(lambda t=title: repo.create(t, today=TODAY)).code == "invalid_title"


def test_acceptance_literals(tmp_path: Path) -> None:
    # Literals: 's status lines with ', ', today=...), create(', ', today=...) and create(',
    # ', today=...) raise AdrError with code == '
    repo = AdrRepository(tmp_path)
    assert repo.create("Café", today=TODAY).path.name == "0001-cafe.md"


def test_cafe_slug(tmp_path: Path) -> None:
    repo = AdrRepository(tmp_path)
    assert repo.create("Caf\u00e9", today=TODAY).path.name == "0001-cafe.md"


@pytest.mark.parametrize("title", ["", "!!", "a\nb", "\u65e5\u672c", "x" * 201])
def test_invalid_titles(tmp_path: Path, title: str) -> None:
    repo = AdrRepository(tmp_path)
    assert caught(lambda: repo.create(title, today=TODAY)).code == "invalid_title"
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(
    ("title", "name"),
    [
        ("Use Postgres!!", "0001-use-postgres.md"),
        ("Caf\u00e9", "0001-cafe.md"),
        ("  Hello,   World  ", "0001-hello-world.md"),
        ("x" * 200, "0001-" + "x" * 60 + ".md"),
    ],
)
def test_slugs(tmp_path: Path, title: str, name: str) -> None:
    created = AdrRepository(tmp_path).create(title, today=TODAY)
    assert created.path.name == name


def test_long_slug_has_no_trailing_dash(tmp_path: Path) -> None:
    created = AdrRepository(tmp_path).create("word " * 30, today=TODAY)
    slug = created.path.name[5:-3]
    assert len(slug) <= 60
    assert not slug.endswith("-")


BASE = adr_text(1, "Title")


def broken(old: str, new: str) -> str:
    assert old in BASE
    return BASE.replace(old, new, 1)


FORMAT_CASES = [
    ("", 1),
    (broken("# 1. Title", "#1. Title"), 1),
    (broken("# 1. Title", "# 01. Title"), 1),
    (broken("# 1. Title", "# 1. "), 1),
    (broken("# 1. Title", "# 10000. Title"), 1),
    (broken("# 1. Title\n\n", "# 1. Title\nx\n"), 2),
    (broken("2026-01-02", "2026-02-30"), 3),
    (broken("2026-01-02", "2026-1-2"), 3),
    (broken("Date: 2026-01-02", "date: 2026-01-02"), 3),
    (broken("2026-01-02\n\n", "2026-01-02\nx\n"), 4),
    (broken("## Status", "## State"), 5),
    (broken("## Status\n\n", "## Status\nx\n"), 6),
    (broken("Accepted\n", ""), 5),
    (broken("Accepted", "Maybe"), 7),
    (broken("Accepted\n", "Accepted\nProposed\n"), 8),
    (broken("Accepted", "Accepted\nSuperseded by [2. B](0002-b.md)"), 7),
    (broken("Accepted", "Accepted\n" + "x" * 1025), 8),
    (broken("Accepted", "Accepted\nAmends [x](y)"), 8),
]


@pytest.mark.parametrize(("text", "line"), FORMAT_CASES)
def test_parse_adr_rejects_malformed_text(text: str, line: int) -> None:
    exc = caught(lambda: parse_adr(text, Path("0001-title.md")))
    assert exc.code == "format"
    assert exc.line == line


def test_parse_adr_reads_every_field() -> None:
    extra = "\nSupersedes [2. Old](0002-old.md)\nAmends [3. X](0003-x.md)\n"
    text = adr_text(1, "A [b](c) d", status="accepted", extra=extra)
    path = Path("0001-a.md")
    expected = Adr(
        1,
        "A [b](c) d",
        "Accepted",
        date(2026, 1, 2),
        path,
        (Link("Supersedes", 2), Link("Amends", 3)),
    )
    assert parse_adr(text, path) == expected
    assert parse_adr(text.replace("\n", "\r\n"), path) == expected


def test_parse_adr_reads_superseded_by_link() -> None:
    text = adr_text(4, "X", status="Superseded by [5. Y](0005-y.md)")
    adr = parse_adr(text, Path("0004-x.md"))
    assert adr.status == "Superseded"
    assert adr.links == (Link("Superseded by", 5),)


def test_parse_adr_enforces_the_size_limit() -> None:
    path = Path("0001-a.md")
    assert caught(lambda: parse_adr("x" * (256 * 1024 + 1), path)).code == "too_large"
    assert caught(lambda: parse_adr("\u00e9" * 131073, path)).code == "too_large"


def test_get_and_missing_numbers(tmp_path: Path) -> None:
    repo = AdrRepository(tmp_path / "missing")
    assert repo.list() == []
    assert caught(lambda: repo.get(1)).code == "not_found"
    seed(tmp_path)
    repo = AdrRepository(tmp_path)
    assert repo.root == tmp_path
    assert repo.get(2).title == "Old title"
    assert repo.get(2).path == tmp_path / "0002-old-title.md"
    for number in (0, 4, 10000):
        assert caught(lambda n=number: repo.get(n)).code == "not_found"


def test_create_makes_missing_directories(tmp_path: Path) -> None:
    repo = AdrRepository(tmp_path / "doc" / "adr")
    created = repo.create("First", today=TODAY, status="accepted")
    assert created.status == "Accepted"
    assert created.path.exists()


def test_malformed_repositories(tmp_path: Path) -> None:
    put(tmp_path, "0001-a.md", adr_text(1, "A"))
    put(tmp_path, "0001-b.md", adr_text(1, "B"))
    repo = AdrRepository(tmp_path)
    assert caught(repo.list).code == "format"
    assert caught(lambda: repo.get(1)).code == "format"


def test_header_number_must_match_the_file_name(tmp_path: Path) -> None:
    put(tmp_path, "0002-x.md", adr_text(5, "X"))
    exc = caught(AdrRepository(tmp_path).list)
    assert exc.code == "format"
    assert exc.line == 1


def test_directories_and_bad_encodings_are_refused(tmp_path: Path) -> None:
    (tmp_path / "0001-dir.md").mkdir()
    assert caught(AdrRepository(tmp_path).list).code == "format"
    (tmp_path / "0001-dir.md").rmdir()
    (tmp_path / "0001-bin.md").write_bytes(b"\xff\xfe")
    assert caught(AdrRepository(tmp_path).list).code == "format"


def test_symlinked_adr_files_are_refused(tmp_path: Path) -> None:
    target = put(tmp_path, "target.txt", adr_text(2, "B"))
    try:
        os.symlink(target, tmp_path / "0002-b.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    exc = caught(AdrRepository(tmp_path).list)
    assert exc.code == "format"


def test_oversized_files_are_refused(tmp_path: Path) -> None:
    (tmp_path / "0001-big.md").write_bytes(b"x" * (256 * 1024 + 1))
    assert caught(AdrRepository(tmp_path).list).code == "too_large"


def test_file_count_is_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("0001-a.md", "0002-b.md", "0003-c.md"):
        put(tmp_path, name, "x")
    monkeypatch.setattr(core, "MAX_NUMBER", 2)
    assert caught(AdrRepository(tmp_path).list).code == "too_large"


def test_numbers_are_exhausted_at_10000(tmp_path: Path) -> None:
    put(tmp_path, "9998-old.md", adr_text(9998, "Old"))
    put(tmp_path, "9999-last.md", "x")
    repo = AdrRepository(tmp_path)
    assert caught(lambda: repo.create("Next", today=TODAY)).code == "number_exhausted"
    assert caught(lambda: repo.supersede(9998, "Next", today=TODAY)).code == "number_exhausted"


def test_second_create_of_one_number_conflicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = AdrRepository(tmp_path)
    repo.create("Use Postgres", today=TODAY)
    path = tmp_path / "0001-use-postgres.md"
    before = path.read_bytes()
    monkeypatch.setattr(AdrRepository, "_next_number", lambda self: 1)
    assert caught(lambda: repo.create("Use Postgres", today=TODAY)).code == "conflict"
    assert path.read_bytes() == before


class FullDisk:
    def __enter__(self) -> FullDisk:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def write(self, text: str) -> None:
        raise OSError("no space left")


def test_create_reports_write_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = AdrRepository(tmp_path)

    def refuse(*args: object, **kwargs: object) -> object:
        raise PermissionError("denied")

    monkeypatch.setattr(core, "open", refuse, raising=False)
    assert caught(lambda: repo.create("A", today=TODAY)).code == "write_failed"
    monkeypatch.setattr(core, "open", lambda *a, **k: FullDisk(), raising=False)
    assert caught(lambda: repo.create("A", today=TODAY)).code == "write_failed"


def test_create_fails_when_the_root_is_a_file(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    exc = caught(lambda: AdrRepository(blocker).create("A", today=TODAY))
    assert exc.code == "write_failed"


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_set_status_replaces_only_the_status_line(tmp_path: Path, eol: str) -> None:
    put(tmp_path, "0001-first.md", adr_text(1, "First", status="Proposed", eol=eol))
    updated = AdrRepository(tmp_path).set_status(1, "accepted")
    assert updated.status == "Accepted"
    expected = adr_text(1, "First", eol=eol).encode("utf-8")
    assert (tmp_path / "0001-first.md").read_bytes() == expected


def test_set_status_on_a_missing_adr(tmp_path: Path) -> None:
    assert caught(lambda: AdrRepository(tmp_path).set_status(1, "Accepted")).code == "not_found"


def test_link_appends_after_the_status(tmp_path: Path) -> None:
    seed(tmp_path)
    repo = AdrRepository(tmp_path)
    repo.link(1, 3, "Amends")
    extra = "\nAmends [3. Third](0003-third.md)\n"
    assert (tmp_path / "0001-first.md").read_bytes() == adr_text(1, "First", extra=extra).encode()
    assert repo.get(1).links == (Link("Amends", 3),)
    repo.link(1, 2, " Relates to ")
    assert repo.get(1).links == (Link("Amends", 3), Link("Relates to", 2))
    assert caught(lambda: repo.link(1, 3, "AMENDS")).code == "duplicate_link"


@pytest.mark.parametrize("relation", ["## Decision", "# H", "- item", "> quote", "1. step"])
def test_link_rejects_markdown_structure_in_relation(tmp_path: Path, relation: str) -> None:
    seed(tmp_path)
    exc = caught(lambda: AdrRepository(tmp_path).link(1, 3, relation))
    assert exc.code == "format"


def test_link_keeps_crlf(tmp_path: Path) -> None:
    seed(tmp_path)
    put(tmp_path, "0001-first.md", adr_text(1, "First", eol="\r\n"))
    AdrRepository(tmp_path).link(1, 3, "Amends")
    extra = "\nAmends [3. Third](0003-third.md)\n"
    expected = adr_text(1, "First", extra=extra, eol="\r\n").encode("utf-8")
    assert (tmp_path / "0001-first.md").read_bytes() == expected


def test_link_after_existing_links(tmp_path: Path) -> None:
    put(tmp_path, "0001-a.md", adr_text(1, "A", extra="\nSupersedes [2. B](0002-b.md)\n"))
    put(tmp_path, "0002-b.md", adr_text(2, "B"))
    put(tmp_path, "0003-c.md", adr_text(3, "C"))
    AdrRepository(tmp_path).link(1, 3, "Amends")
    extra = "\nSupersedes [2. B](0002-b.md)\n\nAmends [3. C](0003-c.md)\n"
    assert (tmp_path / "0001-a.md").read_bytes() == adr_text(1, "A", extra=extra).encode()


def test_link_keeps_a_blank_line_before_the_next_heading(tmp_path: Path) -> None:
    head = "# 1. A\n\nDate: 2026-01-02\n\n## Status\n\nAccepted\n"
    put(tmp_path, "0001-a.md", head + "## Context\n\nTODO\n")
    put(tmp_path, "0002-b.md", adr_text(2, "B"))
    AdrRepository(tmp_path).link(1, 2, "Relates to")
    expected = head + "\nRelates to [2. B](0002-b.md)\n\n## Context\n\nTODO\n"
    assert (tmp_path / "0001-a.md\n".strip()).read_text(encoding="utf-8") == expected


def test_link_errors(tmp_path: Path) -> None:
    seed(tmp_path)
    repo = AdrRepository(tmp_path)
    assert caught(lambda: repo.link(1, 1, "Amends")).code == "self_link"
    assert caught(lambda: repo.link(9, 1, "Amends")).code == "not_found"
    assert caught(lambda: repo.link(1, 9, "Amends")).code == "not_found"
    for relation in ("", "[x]", "a\nb", "Superseded by", "x" * 101):
        assert caught(lambda r=relation: repo.link(1, 3, r)).code == "format"
    repo.supersede(2, "New title", today=TODAY)
    repo.link(1, 2, "Relates to")
    assert repo.get(1).links == (Link("Relates to", 2),)


def test_render_index(tmp_path: Path) -> None:
    repo = AdrRepository(tmp_path)
    header = "| Number | Title | Status | Date |\n| --- | --- | --- | --- |\n"
    assert repo.render_index() == header
    repo.create("A|B", today=TODAY, status="accepted")
    repo.create("Second", today=date(2026, 11, 6))
    expected = header + (
        "| 1 | A\\|B | Accepted | 2026-11-05 |\n| 2 | Second | Proposed | 2026-11-06 |\n"
    )
    assert repo.render_index() == expected


def test_cli_init_is_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "doc" / "adr"
    assert cli.main(["--dir", str(target), "init"]) == 0
    assert cli.main(["--dir", str(target), "init"]) == 0
    assert target.is_dir()
    assert "initialized" in capsys.readouterr().out


def test_cli_full_flow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--dir", str(tmp_path)]
    first = [*base, "new", "First", "--status", "accepted", "--date", "2026-01-02"]
    assert cli.main(first) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "0001-first.md")
    assert cli.main([*base, "new", "Second", "--date", "2026-01-03"]) == 0
    assert cli.main([*base, "status", "2", "Rejected"]) == 0
    assert cli.main([*base, "link", "2", "1", "--relation", "Amends"]) == 0
    assert cli.main([*base, "supersede", "1", "Third", "--date", "2026-01-04"]) == 0
    capsys.readouterr()
    repo = AdrRepository(tmp_path)
    assert repo.get(2).status == "Rejected"
    assert repo.get(2).links == (Link("Amends", 1),)
    assert repo.get(1).status == "Superseded"
    assert cli.main([*base, "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert "Superseded" in lines[0]
    assert cli.main([*base, "index"]) == 0
    assert capsys.readouterr().out.startswith("| Number | Title | Status | Date |")


def test_cli_domain_failures_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--dir", str(tmp_path)]
    assert cli.main([*base, "status", "9", "Accepted"]) == 1
    assert "not_found" in capsys.readouterr().err
    seed(tmp_path)
    assert cli.main([*base, "status", "1", "Maybe"]) == 1
    assert "invalid_status" in capsys.readouterr().err
    assert cli.main([*base, "link", "1", "1", "--relation", "Amends"]) == 1
    assert cli.main([*base, "new", "T", "--status", "Maybe"]) == 1
    assert cli.main([*base, "new", "!!"]) == 1


def test_cli_usage_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--dir", str(tmp_path)]
    assert cli.main(base) == 2
    assert cli.main([*base, "new", "T", "--date", "2026-02-30"]) == 2
    assert cli.main([*base, "new", "T", "--date", "nope"]) == 2
    assert cli.main([*base, "list", "--format", "xml"]) == 2
    assert cli.main([*base, "link", "1", "2"]) == 2
    capsys.readouterr()
    assert cli.main(["--help"]) == 0


def test_cli_io_errors_exit_2(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    assert cli.main(["--dir", str(blocker), "list"]) == 2
    assert cli.main(["--dir", str(blocker), "init"]) == 2
    assert cli.main(["--dir", str(blocker), "new", "T"]) == 2


def test_cli_defaults_the_date_to_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_today", lambda: date(2030, 1, 2))
    assert cli.main(["--dir", str(tmp_path), "new", "T"]) == 0
    assert "Date: 2030-01-02" in (tmp_path / "0001-t.md").read_text(encoding="utf-8")
    assert cli.main(["--dir", str(tmp_path), "supersede", "1", "U"]) == 0
    assert "Date: 2030-01-02" in (tmp_path / "0002-u.md").read_text(encoding="utf-8")


def test_cli_today_is_a_real_date() -> None:
    assert isinstance(cli._today(), date)


def test_cli_reads_sys_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["adr", "--dir", str(tmp_path), "init"])
    assert cli.main() == 0
