"""
retailops_cli.files
-------------------
Small file helpers for commands that send multipart uploads.
"""

from __future__ import annotations

import mimetypes
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator

import typer

from .output import err_console


def resolve_file(path: str, *, label: str = "file") -> Path:
    """Return an existing file path or exit with a CLI-friendly error."""
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        err_console.print(f"[red]Error:[/red] {label} not found: [bold]{candidate}[/bold]")
        raise typer.Exit(1)
    return candidate


def guess_mime_type(path: Path) -> str:
    """Guess a content type from the filename with an image-safe fallback."""
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


@contextmanager
def multipart_file(
    field_name: str,
    path: str,
    *,
    label: str = "file",
    content_type: str | None = None,
) -> Iterator[dict]:
    """Open one file and yield an httpx-compatible multipart files mapping."""
    resolved = resolve_file(path, label=label)
    with resolved.open("rb") as handle:
        yield {
            field_name: (
                resolved.name,
                handle,
                content_type or guess_mime_type(resolved),
            )
        }


@contextmanager
def multipart_files(paths: dict[str, str]) -> Iterator[dict]:
    """Open several files and yield an httpx-compatible files mapping."""
    with ExitStack() as stack:
        files = {}
        for field_name, raw_path in paths.items():
            resolved = resolve_file(raw_path, label=field_name)
            handle = stack.enter_context(resolved.open("rb"))
            files[field_name] = (resolved.name, handle, guess_mime_type(resolved))
        yield files
