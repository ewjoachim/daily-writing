import io
import pathlib

import pytest

from daily_writing import artifacts


def test_text_artifact(tmp_path: pathlib.Path):
    artifacts.TextArtifact(path=pathlib.Path("foo"), contents="bar").write(
        destination=tmp_path
    )

    assert (tmp_path / "foo").read_text() == "bar"


def test_html_artifact(tmp_path: pathlib.Path):
    artifacts.HTMLArtifact(path=pathlib.Path("foo"), contents="bar").write(
        destination=tmp_path
    )

    assert (tmp_path / "foo").read_text() == "bar"


def test_bytes_artifact(tmp_path: pathlib.Path):
    artifacts.BytesArtifact(
        path=pathlib.Path("foo"), contents=io.BytesIO(b"bar")
    ).write(destination=tmp_path)

    assert (tmp_path / "foo").read_bytes() == b"bar"


def test_file_artifact(tmp_path: pathlib.Path):
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "bar").write_text("baz")
    artifacts.FileArtifact(
        path=pathlib.Path("qux/bar"),
        source=tmp_path / "foo" / "bar",
    ).write(destination=tmp_path / "frob")

    assert (tmp_path / "frob/qux/bar").read_text() == "baz"


def test_ensure_relative__ok():
    path = pathlib.Path("a")
    assert artifacts.ensure_relative(path) == path


def test_ensure_relative__fail():
    path = pathlib.Path("/a")
    with pytest.raises(ValueError):
        artifacts.ensure_relative(path)
