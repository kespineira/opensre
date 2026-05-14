"""On-disk JSONL source for Claude Code session events.

Claude Code writes ``~/.claude/projects/<mangled-cwd>/<session>.jsonl``
where ``<mangled-cwd>`` is the absolute cwd with ``/`` replaced by
``-``. We tail that file rather than ``/proc/<pid>/fd/1`` because
``tail.py`` rejects TTY targets, and most developers run claude-code
in an interactive terminal.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.agents.probe import cwd_for_pid, open_files_for_pid
from app.agents.token_sources import IncrementalJsonlSource, _PerPidState, safe_mtime

logger = logging.getLogger(__name__)

_DEFAULT_PROJECTS_ROOT = Path.home() / ".claude" / "projects"


class ClaudeCodeJsonlSource(IncrementalJsonlSource):
    def __init__(self, projects_root: Path | None = None) -> None:
        super().__init__()
        self._projects_root = projects_root if projects_root is not None else _DEFAULT_PROJECTS_ROOT

    def _resolve(self, pid: int) -> _PerPidState | None:
        cwd = cwd_for_pid(pid)
        if cwd is None:
            # macOS hardened-runtime apps can deny cwd() even cross-user-same-user;
            # log once at debug rather than spam.
            logger.debug("claude-code source: cwd unavailable for pid %d", pid)
            return None

        project_dir = self._projects_root / _mangle_cwd(cwd)
        try:
            candidates = [path for path in project_dir.iterdir() if path.suffix == ".jsonl"]
        except OSError:
            return None
        if not candidates:
            return None
        session = _session_file_for_pid(pid, candidates, project_dir)
        return self._initial_state_for(session)


def _mangle_cwd(cwd: Path) -> str:
    return str(cwd).replace("/", "-")


def _session_file_for_pid(pid: int, candidates: list[Path], project_dir: Path) -> Path:
    open_jsonl_paths = {
        path
        for path in open_files_for_pid(pid)
        if path.suffix == ".jsonl" and path.parent == project_dir
    }
    matching = [path for path in candidates if path in open_jsonl_paths]
    if matching:
        return max(matching, key=safe_mtime)
    return max(candidates, key=safe_mtime)


__all__ = ["ClaudeCodeJsonlSource"]
