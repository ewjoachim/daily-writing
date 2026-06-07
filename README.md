# Daily Writing

This repo hosts an open source project that let you create a website presenting
daily writings, it was created with challenges like Writober or Writever in mind, but
it's not tied to a specific challenge.

Daily Writing mainly turns a bunch of markdown files (one per writing, at most one per
day), a configuration file, and a directory of static files into a static HTML website
that can be deployed.

Daily Writing offers various features, such as:
- A page for each writing and a homepage. A menu displaying a calendar with all the
  writing for all months.
- Each day is linked to a "prompt" (as in writever/writober prompt), and can have a
  title distinct from the prompt. This is useful if the title of your writing isn't
  excatly the prompt you were given for the day. Also, if your prompts are in a given
  language and the title is the prompt you translated to your language, it's nice.
  The prompt will be displayed in the menu over the title.
- A given writing can span over multiple days and their associated prompts (e.g. if
  you're late), and the calendar will reflect that. Those days may even be
  non-consecutive. It's assumed that the title will be composed of multiple parts each
  related to the associated prompts.
- Each day in a month is linked to a unique color, and the calendar is colored
  accordingly. The homepage displays all the month's colors.
- Posts can be written in advance and will only be published of their date.
- Links to the previous and next writings, for binge-reading.
- Most metadata can be extracted from the name of the file and the writing markdown
  title, but can then be normalized to frontmatter. Having a frontmatter is necessaryÒ when
  using a CMS editor.
- Writings spanning multiple days will have a gradient between the colors of the days.
- A CMS, at `/admin` to update your writings and the site settings directly from your
  browser.
- A RSS feed.
- Nice preview images when you post links to social networks.
- Discreet links to the GitHub source of each writing, to ease online edition or typo
  reporting.
- Privacy-minded Google fonts, downloaded and optimized at build time so that you can
  get various fonts without offering your reader's data to Google (damn, that was a
  mess to code)
- Dark mode. No light mode. Contributions welcome on that.
- Support for extra custom CSS. If you want to add a light mode but just for yourself.
- Support of various locales, for date formats. Apart from dates and numbers, all the
  words that appear on the interface are configurable, so technically, we support all
  languages that Unicode supports.
- If you rename a file but want to keep its original URL too, you can add aliases.
- Site is 100% usable without javascript for users.

Author's personal undying love of handcrafted open source and meticulous yak shaving
went into this project. He likes to think that it shows.

## An example:

https://writober.ewjoach.im/ is deployed from https://github.com/ewjoachim/writober,
using this project.

## Extraction rules

From a single file without a frontmatter, these are the informations being extracted.
Say the file is at `2026/10/03-hello.md` and its content starts with a title that says:
`# 03 - Bonjour`. The system will find that this writing covers a single day
(`2026-10-03`), its prompt is "hello" and its official title is "Bonjour".

Say the file is at `2026/10/03-hello-darkness.md` and its content starts with a title
that says: `# 03&04 - Bonjour, Obscurité`. The system will find that this writing covers
2 days:
- `2026-10-03` for which the prompt is `hello` and the title `Bonjour`,
- `2026-10-04` for which the prompt is `darkness` and the title `Obscurité`.

You can always override those values by editing the frontmatter.

## Installation

### Github

- [Create a repository from the template](https://repo.new?template_name=daily-writing-template&template_owner=ewjoachim)
- Adjust configuration with your details
- Your repository is deployed through GitHub actions (`https://<username>.github.io/<repo name>`)
- Write your stories

### Elsewhere

(Feel free to contribute installation instructions for other platforms).

## Configuration

Your website can be configured through either:

- `daily-writing.toml`,
- `pyproject.toml` within the `[tool.daily-writing]` section
- environments variables,
- CLI flags.

The same options are available in all ways, but they're not spelled out exactly the
same way. In the toml configuration and environment variables, words are
separated by `_` (underscores). In the flags, they're separated by `-` (dashes).
Environment variables are all upper case and prefixed with `DAILY_WRITING_`

Examples:

- `daily-writing.toml`: `server_url = "https://writober.ewjoach.im"`
- environments variables: `SERVER_URL="https://writober.ewjoach.im"`
- CLI flags: `--server-url="https://writober.ewjoach.im"`

The easiest and most up-to-date way to learn about every configuration option is
through: `daily-writing -h`. Feel free to consult [daily-writing.toml](https://github.com/ewjoachim/writober/blob/main/daily-writing.toml) for a working example.

> [!NOTE] There is one extra configuration element: setting the `GITHUB_TOKEN`
> environment variable will help you avoid rate limiting to GitHub's API. It's not added
> in the normal configuration elements to avoid accidentally committing it to your
> repository.

## CLI

There are 2 main subcommands:

- `daily-writing build` builds the website
- `daily-writing serve` launches a local development server that autobuilds the
  website and auto-reload pages in your browser when changes are detected.

## CI/CD Deployment

Solutions like [GitHub Pages](https://docs.github.com/en/pages), [Cloudflare
Pages](https://developers.cloudflare.com/pages/), [GitLab
Pages](https://docs.gitlab.com/user/project/pages/), etc will make your life easier, as
you can edit the markdown files online or push them through git, and have them get
redeployed automatically daily and upon changes.

Here's a GitHub Actions workflow example:

```yaml
name: Deploy

on:
  push:
    branches: ["main"]
  workflow_dispatch:
  schedule:
    - cron: "1 22,23 * 10 *" # Adjust to whenever relvant to you

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Setup Pages
        uses: actions/configure-pages@v5

      - uses: astral-sh/setup-uv@v6

      - name: Sphinx build
        run: uv run daily-writing build

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v4
        with:
          path: _build

  # Deployment job
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

## Adding new content

### Manual
Add and edit your markdown files in the repository via Git or via your
platform's Web interface.

### Online
Daily-Writing can come with a [CMS](https://github.com/sveltia/sveltia-cms), allowing
you to get a nice admin interface that doesn't require to interact with Git.

Integration is not yet 100% streamlined, but it's coming.
