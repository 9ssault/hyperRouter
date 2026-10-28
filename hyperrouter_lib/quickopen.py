"""Small project-file indexing helpers used by the TUI quick-open picker."""

import re
import time
from pathlib import Path
from typing import Iterable


_FILE_QUERY = re.compile(r"(?:^|\s)@([\w./-]*)$")


def index_project_files(root: Path, *, skip: set[str], limit: int = 5000) -> list[str]:
    """Return a deterministic, bounded list of project-relative regular files."""
    found: list[str] = []
    try:
        for path in root.rglob("*"):
            if len(found) >= limit:
                break
            if any(part in skip for part in path.parts) or not path.is_file():
                continue
            found.append(str(path.relative_to(root)))
    except OSError:
        pass
    return sorted(found)


def match_project_files(paths: Iterable[str], query: str, *, limit: int = 8) -> list[str]:
    """Prefer path-prefix matches, then fuzzy character-presence matches."""
    needle = query.lower()
    prefix: list[str] = []
    fuzzy: list[str] = []
    for relative in paths:
        lowered = relative.lower()
        if lowered.startswith(needle):
            prefix.append(relative)
            if len(prefix) >= limit:
                break
        elif needle and len(fuzzy) < limit and all(char in lowered for char in needle):
            fuzzy.append(relative)
    return (prefix or fuzzy)[:limit]


class TuiQuickOpenMixin:
    """Project-aware @file completion and conversation reset for the TUI."""

    def _file_index(self) -> list[str]:
        if self.file_index is not None and time.monotonic() - self.file_index_at < 30:
            return self.file_index
        skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
                ".mypy_cache", ".pytest_cache", "target", ".next"}
        self.file_index = index_project_files(Path.cwd(), skip=skip)
        self.file_index_at = time.monotonic()
        return self.file_index

    def _refresh_file_matches(self) -> None:
        self.file_matches = []
        match = _FILE_QUERY.search(self.buffer)
        if not match:
            return
        self.file_matches = match_project_files(self._file_index(), match.group(1))
        self.file_match_index = 0

    def _complete_file(self) -> None:
        if not self.file_matches:
            self._refresh_file_matches()
        if not self.file_matches:
            return
        choice = self.file_matches[self.file_match_index % len(self.file_matches)]
        self.buffer = _FILE_QUERY.sub(
            lambda match: match.group(0)[:match.start(1) - match.start(0)] + choice,
            self.buffer,
        )
        self.file_matches = []
