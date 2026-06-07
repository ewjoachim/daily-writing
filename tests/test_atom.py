import datetime
import pathlib

from daily_writing import atom


def test_feed(dw_settings):
    feed = atom.Feed(
        settings=dw_settings(
            atom_path="foo.xml",
            author="Bob",
            description="Fooooo",
        ),
        updated=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
    )

    feed.add_entry(
        item_id="123",
        title="Bar !",
        link="https://foo.bar/bar",
        date=datetime.date(2020, 1, 1),
    )

    artifact = feed.get_artifact()
    assert artifact.path == pathlib.Path("foo.xml")
    xml = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fr_FR">
  <id>https://foo.bar/</id>
  <title>Site Name</title>
  <updated>2020-01-01T00:00:00+00:00</updated>
  <author>
    <name>Bob</name>
  </author>
  <link href="https://foo.bar/" rel="self"/>
  <generator uri="https://lkiesow.github.io/python-feedgen" version="1.0.0">python-feedgen</generator>
  <subtitle>Fooooo</subtitle>
  <entry>
    <id>123</id>
    <title>Bar !</title>
    <updated>2020-01-01T00:00:00+01:00</updated>
    <link href="https://foo.bar/bar"/>
  </entry>
</feed>
"""
    assert artifact.contents.getvalue().decode() == xml


def test_feed__minimal(dw_settings):
    feed = atom.Feed(
        settings=dw_settings(atom_path="foo.xml"),
        updated=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
    )

    feed.add_entry(
        item_id="123",
        title="Bar !",
        link="https://foo.bar/bar",
        date=datetime.date(2020, 1, 1),
    )

    artifact = feed.get_artifact()
    assert artifact.path == pathlib.Path("foo.xml")
    xml = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fr_FR">
  <id>https://foo.bar/</id>
  <title>Site Name</title>
  <updated>2020-01-01T00:00:00+00:00</updated>
  <link href="https://foo.bar/" rel="self"/>
  <generator uri="https://lkiesow.github.io/python-feedgen" version="1.0.0">python-feedgen</generator>
  <entry>
    <id>123</id>
    <title>Bar !</title>
    <updated>2020-01-01T00:00:00+01:00</updated>
    <link href="https://foo.bar/bar"/>
  </entry>
</feed>
"""
    assert artifact.contents.getvalue().decode() == xml
