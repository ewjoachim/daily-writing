from __future__ import annotations

import io
import pathlib
from typing import override

import pydantic
from pydantic import dataclasses as pdataclasses


@pdataclasses.dataclass(kw_only=True)
class TextArtifact:
    path: pathlib.Path
    contents: str

    def write(self, dir: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (dir / self.path).parent.mkdir(exist_ok=True, parents=True)
        (dir / self.path).write_text(self.contents)


@pdataclasses.dataclass(kw_only=True)
class HTMLArtifact(TextArtifact):
    @override
    def write(self, dir: pathlib.Path):
        super().write(dir=dir)


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class BytesArtifact:
    path: pathlib.Path
    contents: io.BytesIO

    def write(self, dir: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (dir / self.path).parent.mkdir(exist_ok=True, parents=True)
        (dir / self.path).write_bytes(self.contents.getvalue())


@pdataclasses.dataclass(kw_only=True)
class FileArtifact:
    path: pathlib.Path
    source: pathlib.Path
    destination: pathlib.Path

    def write(self, dir: pathlib.Path):
        rel = self.path.relative_to(self.source)
        destination = dir / self.destination / rel
        destination.parent.mkdir(exist_ok=True, parents=True)
        self.path.copy(destination)
