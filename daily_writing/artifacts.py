import io
import pathlib
from typing import Protocol, override

import pydantic
from pydantic import dataclasses as pdataclasses


class BaseArtifact(Protocol):
    def write(self, destination: pathlib.Path): ...


@pdataclasses.dataclass(kw_only=True)
class TextArtifact:
    path: pathlib.Path
    contents: str

    def write(self, destination: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (destination / self.path).parent.mkdir(exist_ok=True, parents=True)
        (destination / self.path).write_text(self.contents)


@pdataclasses.dataclass(kw_only=True)
class HTMLArtifact(TextArtifact):
    @override
    def write(self, destination: pathlib.Path):
        super().write(destination=destination)


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class BytesArtifact:
    path: pathlib.Path
    contents: io.BytesIO

    def write(self, destination: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (destination / self.path).parent.mkdir(exist_ok=True, parents=True)
        (destination / self.path).write_bytes(self.contents.getvalue())


@pdataclasses.dataclass(kw_only=True)
class FileArtifact:
    path: pathlib.Path
    source: pathlib.Path

    def write(self, destination: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (destination / self.path).parent.mkdir(exist_ok=True, parents=True)
        self.source.copy(destination / self.path)
