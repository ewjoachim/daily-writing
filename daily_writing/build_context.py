from pydantic import dataclasses as pdataclasses


@pdataclasses.dataclass(kw_only=True)
class BuildContext:
    inject_hot_reload_js: bool = False
