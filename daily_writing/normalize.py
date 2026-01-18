from __future__ import annotations

import logging

import flowmark
import frontmatter

from . import models
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


def normalize(settings: settings_module.Settings) -> None:
    """
    Add frontmatter to writings that don't have it (can be forced), extracting metadata
    from filename and content
    """
    if not settings.normalize:
        raise NotImplementedError()

    modified = 0
    paths = {path.absolute() for path in settings.normalize.paths}

    for writing in models.Writing.get_all_writings(
        settings=settings, restrict_to_paths=set(paths)
    ):
        paths -= {writing.markdown_file.md_path}
        logger.debug(f"Normalizing {writing.markdown_file.md_path}")
        modified += int(
            normalize_writing(writing=writing, rewrite=settings.normalize.rewrite)
        )

    if paths:
        logger.warning(
            f"Ignored following file(s) not found: {', '.join(f'{e}' for e in paths)}"
        )
    logger.info(f"Normalized {modified} writings.")


def normalize_writing(writing: models.Writing, rewrite: bool) -> bool:
    markdown_file = writing.markdown_file

    if markdown_file.writing_metadata.model_dump(exclude_defaults=True) and not rewrite:
        logger.debug(f"Already has metadata, skipping: {writing.md_path}")
        return False

    post = markdown_file.post

    prompts = [
        models.PartialPrompt(
            title=prompt.title,
            original_prompt=prompt.original_prompt,
            date=prompt.date,
        )
        for prompt in writing.prompts
    ]

    front_matter = models.MultiplePromptsFrontMatter(
        full_title=writing.full_title,
        prompts=prompts,
    )

    new_metadata = front_matter.model_dump(exclude_defaults=True)

    if not new_metadata:
        logger.debug(f"No metadata to add for {writing.md_path}")
        return False

    body = post.content

    # Create new post with frontmatter
    new_post = frontmatter.Post(content=body, **new_metadata)

    # Write back with trailing newline
    # Remove the blank line between the frontmatter and the post (for compatibility
    # with flowmark)
    new_content = flowmark.reformat_text(
        frontmatter.dumps(post=new_post) + "\n",
        ellipses=True,
        cleanups=True,
    )

    if new_content == writing.md_path.read_text():
        logger.debug(f"No changes for {writing.md_path}")
        return False

    writing.md_path.write_text(new_content)
    logger.info(f"Normalized: {writing.md_path}")

    return True
