
def cms_artifacts(
    settings: settings_module.Settings,
) -> Iterator[artifacts.BaseArtifact]:
    script_path = settings.build_cms_dir / "script.js"
    yield artifacts.BytesArtifact(
        contents=io.BytesIO(
            get_cms_script(
                sveltia_version=settings.sveltia_version,
                cache_dir=settings.cache_dir,
            )
        ),
        path=script_path,
    )
    config_url = settings.build_cms_dir / "config.json"
    yield artifacts.TextArtifact(
        path=settings.build_cms_dir / "index.html",
        contents=get_cms_index(
            title=f"{settings.site_name} - Admin",
            script_url=f"/{script_path}",
            config_url=f"/{config_url}",
        ),
    )
    yield artifacts.TextArtifact(
        path=config_url,
        contents=get_cms_config(settings=settings),
    )


def get_cms_script(sveltia_version: str, cache_dir: pathlib.Path) -> bytes:
    cache_file = cache_dir / f"sveltia-{sveltia_version}.js"
    if sveltia_version != "latest" and cache_file.exists():
        logger.info(f"Using cached Sveltia CMS version {sveltia_version}")
        return cache_file.read_bytes()

    cms_script_url = (
        f"https://unpkg.com/@sveltia/cms@{sveltia_version}/dist/sveltia-cms.js"
    )
    logger.debug(f"Downloading Sveltia @ {sveltia_version} from {cms_script_url}")
    response = httpx.get(cms_script_url, follow_redirects=True)
    response.raise_for_status()
    final_version = response.url.path.split("@", 1)[-1].split("/", 1)[0]
    logger.info(f"Using Sveltia CMS version {final_version} from {response.url}")
    result = response.content
    cache_file.write_bytes(result)
    return result


def get_cms_index(title: str, script_url: str, config_url: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="robots" content="noindex" />
    <title>{title}</title>
    <link href="{config_url}" type="application/json" rel="cms-config-url" />
  </head>
  <body>
    <script src="{script_url}"></script>
  </body>
</html>"""


def get_cms_config(settings: settings_module.Settings) -> str:

    config = {
        "media_folder": f"/{settings.build_static_dir}",
        "public_folder": f"/{settings.build_static_dir}",
        "singletons": [get_config_collection()],
        "collections": [get_writings_collection()],
        "site_url": str(settings.site_full_url),
        "logo": {"src": f"/{settings.source_static_dir / settings.logo}"},
        "app_title": f"{settings.site_name} - Admin",
        "editor": {"preview": False},
        "output": {
            "omit_empty_optional_fields": True,
        },
    }
    config = utils.deep_merge(config, settings.cms_config)
    return json.dumps(config, indent=2)

