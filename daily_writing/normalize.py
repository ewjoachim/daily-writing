import logging
from typing import Any, override

import flowmark
import frontmatter
import yaml

from . import models
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


class NoAliasDumper(yaml.SafeDumper):
    @override
    def ignore_aliases(self, data: Any) -> bool:
        return True


def normalize(settings: settings_module.CLISettings) -> None:
    """
    Make the metadata detected from filename and content explicit in the frontmatter
    (never changing detected values), and reformat writings with flowmark
    """
    if not settings.normalize:
        raise NotImplementedError()

    modified = 0
    paths = {path.resolve() for path in settings.normalize.paths}

    for writing in models.Writing.get_all_writings(
        settings=settings, restrict_to_paths=set(paths)
    ):
        paths -= {writing.markdown_file.md_path.resolve()}
        logger.debug(f"Normalizing {writing.markdown_file.md_path}")
        modified += int(normalize_writing(writing=writing))

    if paths:
        logger.warning(
            f"Ignored following file(s) not found: {', '.join(f'{e}' for e in paths)}"
        )
    logger.info(f"Normalized {modified} writings.")


def explicit_metadata(writing: models.Writing) -> dict[str, Any]:
    metadata = dict(writing.markdown_file.post.metadata)

    if "prompts" not in metadata:
        metadata.pop("title", None)
        metadata.pop("original_prompt", None)

    metadata["prompts"] = [
        models.PartialPrompt(
            title=prompt.title or None,
            original_prompt=prompt.original_prompt,
            date=prompt.date,
        ).model_dump(exclude_defaults=True)
        for prompt in writing.prompts
    ]
    if not metadata.get("full_title"):
        metadata["full_title"] = writing.full_title
    if not metadata.get("date"):
        metadata["date"] = writing.first_date

    return metadata


def normalize_writing(writing: models.Writing) -> bool:
    post = frontmatter.Post(
        content=writing.markdown_file.post.content, **explicit_metadata(writing)
    )
    new_content = flowmark.reformat_text(
        frontmatter.dumps(post=post, Dumper=NoAliasDumper) + "\n",
        ellipses=True,
        cleanups=True,
    )

    if new_content == writing.md_path.read_text(encoding="utf-8"):
        logger.debug(f"No changes for {writing.md_path}")
        return False

    writing.md_path.write_text(new_content, encoding="utf-8")
    logger.info(f"Normalized: {writing.md_path}")

    return True
