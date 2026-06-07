import io
import pathlib
from typing import Annotated, Protocol, override

import pydantic
from pydantic import dataclasses as pdataclasses


class BaseArtifact(Protocol):
    def write(self, destination: pathlib.Path): ...


def ensure_relative(path: pathlib.Path):
    if path.is_absolute():
        raise ValueError("Only relative paths are accepted")

    return path


@pdataclasses.dataclass(kw_only=True)
class TextArtifact:
    path: Annotated[pathlib.Path, pydantic.AfterValidator(ensure_relative)]
    contents: str

    def write(self, destination: pathlib.Path):
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
    path: Annotated[pathlib.Path, pydantic.AfterValidator(ensure_relative)]
    contents: io.BytesIO

    def write(self, destination: pathlib.Path):
        (destination / self.path).parent.mkdir(exist_ok=True, parents=True)
        (destination / self.path).write_bytes(self.contents.getvalue())


@pdataclasses.dataclass(kw_only=True)
class FileArtifact:
    path: Annotated[pathlib.Path, pydantic.AfterValidator(ensure_relative)]
    source: pathlib.Path

    def write(self, destination: pathlib.Path):
        (destination / self.path).parent.mkdir(exist_ok=True, parents=True)
        self.source.copy(destination / self.path)
