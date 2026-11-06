"""Core model, parser and repository for Architecture Decision Records."""

from __future__ import annotations

import builtins
import contextlib
import datetime
import logging
import os
import re
import stat
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, NoReturn

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

ErrorCode = Literal[
    "not_found",
    "format",
    "invalid_status",
    "invalid_title",
    "duplicate_link",
    "self_link",
    "already_superseded",
    "conflict",
    "number_exhausted",
    "too_large",
    "write_failed",
]

MAX_FILE_BYTES = 256 * 1024
MAX_NUMBER = 9999
MAX_SLUG_LENGTH = 60
MAX_TITLE_LENGTH = 200
MAX_RELATION_LENGTH = 100
MAX_LINE_LENGTH = 1024
MAX_QUOTE = 200

SUPERSEDED = "Superseded"
SUPERSEDED_BY = "Superseded by"
SUPERSEDES = "Supersedes"
SETTABLE_STATUSES = ("Proposed", "Accepted", "Rejected", "Deprecated")

_STATUS_BY_LOWER = {name.lower(): name for name in (*SETTABLE_STATUSES, SUPERSEDED)}
_SETTABLE_BY_LOWER = {name.lower(): name for name in SETTABLE_STATUSES}

_NAME_RE = re.compile(r"[0-9]{4}-[a-z0-9-]+\.md")
_HEADER_RE = re.compile(r"# ([1-9][0-9]{0,3})\. (\S.*)")
_DATE_RE = re.compile(r"Date: ([0-9]{4})-([0-9]{2})-([0-9]{2})")
_LINK_RE = re.compile(r"([^\[\]]+?) \[([1-9][0-9]{0,3})\. .*\]\([0-9]{4}-[a-z0-9-]+\.md\)")


class AdrError(Exception):
    """Base error of the library; ``code`` is a stable machine-readable identifier."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        path: Path | None = None,
        line: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.path = path
        self.line = line


@dataclass(frozen=True)
class Link:
    """A typed reference from one ADR to another."""

    relation: str
    target: int


@dataclass(frozen=True)
class Adr:
    """A parsed Architecture Decision Record."""

    number: int
    title: str
    status: str
    date: datetime.date
    path: Path
    links: tuple[Link, ...] = ()


@dataclass(frozen=True)
class _Parsed:
    adr: Adr
    status_idx: int | None
    last_idx: int


def _clip(value: str) -> str:
    return "".join(ch if ch.isprintable() else "?" for ch in value[:MAX_QUOTE])


def _fail(path: Path | None, index: int, message: str) -> NoReturn:
    raise AdrError("format", message, path=path, line=index + 1)


def _at(lines: list[str], index: int) -> str | None:
    return lines[index] if index < len(lines) else None


def _has_control(text: str) -> bool:
    return any(unicodedata.category(ch).startswith("C") for ch in text)


def _plain_date(value: datetime.date) -> datetime.date:
    return datetime.date(value.year, value.month, value.day)


def _parse(text: str, path: Path) -> _Parsed:
    too_big = len(text) > MAX_FILE_BYTES
    if too_big or len(text.encode("utf-8", "surrogatepass")) > MAX_FILE_BYTES:
        raise AdrError("too_large", "ADR text exceeds the size limit", path=path)
    lines = [part[:-1] if part.endswith("\r") else part for part in text.split("\n")]
    header = _HEADER_RE.fullmatch(lines[0])
    if header is None:
        _fail(path, 0, "first line must be '# N. Title'")
    if _at(lines, 1) != "":
        _fail(path, 1, "line 2 must be blank")
    date_match = _DATE_RE.fullmatch(_at(lines, 2) or "")
    if date_match is None:
        _fail(path, 2, "line 3 must be 'Date: YYYY-MM-DD'")
    try:
        day = datetime.date(int(date_match[1]), int(date_match[2]), int(date_match[3]))
    except ValueError:
        _fail(path, 2, "the date is not a real calendar date")
    if _at(lines, 3) != "":
        _fail(path, 3, "line 4 must be blank")
    if _at(lines, 4) != "## Status":
        _fail(path, 4, "line 5 must be '## Status'")
    if _at(lines, 5) != "":
        _fail(path, 5, "line 6 must be blank")
    links: list[Link] = []
    status_word: str | None = None
    status_idx: int | None = None
    last_idx = 5
    index = 6
    while index < len(lines) and not lines[index].startswith("## "):
        content = lines[index].strip()
        if content:
            if len(content) > MAX_LINE_LENGTH:
                _fail(path, index, "status line is too long")
            last_idx = index
            link = _LINK_RE.fullmatch(content)
            if link is not None:
                links.append(Link(link[1].strip(), int(link[2])))
            elif status_word is None and content.lower() in _STATUS_BY_LOWER:
                status_word = _STATUS_BY_LOWER[content.lower()]
                status_idx = index
            else:
                _fail(path, index, f"unexpected status line: '{_clip(content)}'")
        index += 1
    if any(item.relation.lower() == "superseded by" for item in links):
        if status_word not in (None, SUPERSEDED):
            _fail(path, status_idx or 0, "status contradicts a 'Superseded by' link")
        status = SUPERSEDED
    elif status_word is None:
        _fail(path, 4, "the status section has no status")
    else:
        status = status_word
    adr = Adr(
        number=int(header[1]),
        title=header[2].strip(),
        status=status,
        date=day,
        path=path,
        links=tuple(links),
    )
    return _Parsed(adr, status_idx, last_idx)


def parse_adr(text: str, path: Path) -> Adr:
    """Parse the text of an ADR file; raise AdrError('format' or 'too_large') on bad input."""
    return _parse(text, path).adr


def _slugify(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].strip("-")


def _validate_title(title: str) -> tuple[str, str]:
    clean = title.strip()
    if not clean:
        raise AdrError("invalid_title", "the title must not be empty")
    if len(clean) > MAX_TITLE_LENGTH:
        raise AdrError("invalid_title", f"the title exceeds {MAX_TITLE_LENGTH} characters")
    if _has_control(clean):
        raise AdrError("invalid_title", "the title must not contain control characters")
    slug = _slugify(clean)
    if not slug:
        raise AdrError("invalid_title", "the title has no ASCII letters or digits")
    return clean, slug


def _validate_status(status: str) -> str:
    canonical = _SETTABLE_BY_LOWER.get(status.strip().lower())
    if canonical is None:
        allowed = ", ".join(SETTABLE_STATUSES)
        message = f"status must be one of {allowed}: got '{_clip(status)}'"
        raise AdrError("invalid_status", message)
    return canonical


def _validate_relation(relation: str) -> str:
    clean = relation.strip()
    if not clean or len(clean) > MAX_RELATION_LENGTH:
        raise AdrError("format", "the link relation must be 1-100 characters")
    if "[" in clean or "]" in clean or _has_control(clean):
        raise AdrError("format", "the link relation has forbidden characters")
    if clean[0] in "#->" or clean[0].isdigit():
        raise AdrError("format", "the link relation must start with a letter")
    if clean.lower() == "superseded by":
        raise AdrError("format", "'Superseded by' is reserved for supersede")
    return clean


def _render(number: int, title: str, status: str, day: datetime.date, link: str | None) -> str:
    status_block = f"{status}\n"
    if link is not None:
        status_block += f"\n{link}\n"
    return (
        f"# {number}. {title}\n\nDate: {day.isoformat()}\n\n## Status\n\n{status_block}\n"
        "## Context\n\nTODO\n\n## Decision\n\nTODO\n\n## Consequences\n\nTODO\n"
    )


def _replace_line(text: str, index: int, content: str) -> str:
    lines = text.split("\n")
    suffix = "\r" if lines[index].endswith("\r") else ""
    lines[index] = content + suffix
    return "\n".join(lines)


def _open_status_index(parsed: _Parsed) -> int:
    index = parsed.status_idx
    if parsed.adr.status == SUPERSEDED or index is None:
        message = f"ADR {parsed.adr.number} is superseded and can no longer change"
        raise AdrError("already_superseded", message, path=parsed.adr.path)
    return index


def _read(path: Path) -> str:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        raise AdrError("format", "symlinked ADR files are refused", path=path)
    if not stat.S_ISREG(info.st_mode):
        raise AdrError("format", "the ADR path is not a regular file", path=path)
    with open(path, "rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise AdrError("too_large", "ADR file exceeds the size limit", path=path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise AdrError("format", "the ADR file is not valid UTF-8", path=path) from None


class AdrRepository:
    """A directory of ADR files named NNNN-slug.md.

    Read operations may raise OSError for I/O problems; write operations wrap them in
    AdrError('write_failed').
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """The directory that holds the ADR files."""
        return self._root

    def _entries(self) -> builtins.list[tuple[int, str]]:
        found: builtins.list[tuple[int, str]] = []
        try:
            with os.scandir(self._root) as entries:
                for entry in entries:
                    if _NAME_RE.fullmatch(entry.name):
                        found.append((int(entry.name[:4]), entry.name))
                        if len(found) > MAX_NUMBER:
                            message = "too many ADR files"
                            raise AdrError("too_large", message, path=self._root)
        except FileNotFoundError:
            return []
        found.sort()
        return found

    def _load(self, name: str) -> tuple[_Parsed, str]:
        path = self._root / name
        text = _read(path)
        parsed = _parse(text, path)
        if parsed.adr.number != int(name[:4]):
            _fail(path, 0, "the header number does not match the file name")
        return parsed, text

    def _get_full(self, number: int) -> tuple[_Parsed, str]:
        if not 1 <= number <= MAX_NUMBER:
            raise AdrError("not_found", f"ADR {number} does not exist")
        names = [name for num, name in self._entries() if num == number]
        if not names:
            raise AdrError("not_found", f"ADR {number} does not exist")
        if len(names) > 1:
            raise AdrError("format", f"more than one file has number {number}", path=self._root)
        return self._load(names[0])

    def _next_number(self) -> int:
        entries = self._entries()
        number = (entries[-1][0] if entries else 0) + 1
        if number > MAX_NUMBER:
            raise AdrError("number_exhausted", "no ADR numbers are left", path=self._root)
        return number

    def _create_file(
        self,
        title: str,
        slug: str,
        status: str,
        day: datetime.date,
        target: Adr | None = None,
    ) -> Adr:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            message = "cannot create the ADR directory"
            raise AdrError("write_failed", message, path=self._root) from exc
        number = self._next_number()
        path = self._root / f"{number:04d}-{slug}.md"
        links: tuple[Link, ...] = ()
        line = None
        if target is not None:
            line = f"{SUPERSEDES} [{target.number}. {target.title}]({target.path.name})"
            links = (Link(SUPERSEDES, target.number),)
        content = _render(number, title, status, day, line)
        created = False
        try:
            with open(path, "x", encoding="utf-8", newline="\n") as handle:
                created = True
                handle.write(content)
        except FileExistsError as exc:
            raise AdrError("conflict", f"ADR {number} already exists", path=path) from exc
        except OSError as exc:
            if created:
                with contextlib.suppress(OSError):
                    path.unlink()
            raise AdrError("write_failed", "could not write the ADR file", path=path) from exc
        logger.debug("created ADR %d", number)
        return Adr(number, title, status, day, path, links)

    def _atomic_write(self, path: Path, text: str) -> None:
        tmp_name: str | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(prefix=".adr-", suffix=".tmp", dir=self._root)
            with os.fdopen(fd, "wb") as handle:
                handle.write(text.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            with contextlib.suppress(OSError):
                os.chmod(tmp_name, stat.S_IMODE(os.stat(path).st_mode))
            os.replace(tmp_name, path)
        except OSError as exc:
            if tmp_name is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_name)
            raise AdrError("write_failed", "could not update the ADR file", path=path) from exc
        logger.debug("updated ADR file %s", path.name)

    def list(self) -> builtins.list[Adr]:
        """Return every ADR sorted by number."""
        result: builtins.list[Adr] = []
        previous: int | None = None
        for number, name in self._entries():
            if number == previous:
                _fail(self._root / name, 0, f"more than one file has number {number}")
            previous = number
            result.append(self._load(name)[0].adr)
        return result

    def get(self, number: int) -> Adr:
        """Return one ADR; raise AdrError('not_found') when it does not exist."""
        return self._get_full(number)[0].adr

    def create(self, title: str, *, today: datetime.date, status: str = "Proposed") -> Adr:
        """Create the next ADR with an exclusive create; the date is injected by the caller."""
        clean, slug = _validate_title(title)
        canonical = _validate_status(status)
        return self._create_file(clean, slug, canonical, _plain_date(today))

    def set_status(self, number: int, status: str) -> Adr:
        """Set Proposed, Accepted, Rejected or Deprecated on a non-superseded ADR."""
        canonical = _validate_status(status)
        parsed, text = self._get_full(number)
        index = _open_status_index(parsed)
        self._atomic_write(parsed.adr.path, _replace_line(text, index, canonical))
        return replace(parsed.adr, status=canonical)

    def supersede(self, old: int, new_title: str, *, today: datetime.date) -> Adr:
        """Create a new ADR that supersedes ``old`` and mark ``old`` as superseded."""
        parsed, text = self._get_full(old)
        index = _open_status_index(parsed)
        title, slug = _validate_title(new_title)
        created = self._create_file(title, slug, "Proposed", _plain_date(today), parsed.adr)
        marker = f"{SUPERSEDED_BY} [{created.number}. {created.title}]({created.path.name})"
        self._atomic_write(parsed.adr.path, _replace_line(text, index, marker))
        return created

    def link(self, source: int, target: int, relation: str) -> None:
        """Append a ``relation [N. Title](file)`` line to the status section of ``source``."""
        clean = _validate_relation(relation)
        if source == target:
            raise AdrError("self_link", f"ADR {source} cannot link to itself")
        parsed, text = self._get_full(source)
        _open_status_index(parsed)
        dest = self.get(target)
        key = clean.lower()
        existing = parsed.adr.links
        if any(item.target == target and item.relation.lower() == key for item in existing):
            message = f"ADR {source} already has a '{clean}' link to ADR {target}"
            raise AdrError("duplicate_link", message, path=parsed.adr.path)
        line = f"{clean} [{dest.number}. {dest.title}]({dest.path.name})"
        lines = text.split("\n")
        cr = "\r" if "\r\n" in text else ""
        at = parsed.last_idx + 1
        insert = [cr, line + cr]
        following = _at(lines, at)
        if following is not None and following.strip():
            insert.append(cr)
        lines[at:at] = insert
        self._atomic_write(parsed.adr.path, "\n".join(lines))

    def render_index(self) -> str:
        """Return a Markdown table of every ADR."""
        rows = ["| Number | Title | Status | Date |", "| --- | --- | --- | --- |"]
        for item in self.list():
            title = item.title.replace("|", "\\|")
            rows.append(f"| {item.number} | {title} | {item.status} | {item.date.isoformat()} |")
        return "\n".join(rows) + "\n"
