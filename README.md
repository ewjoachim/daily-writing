# Daily Writing

This repo hosts a set of open source tools that let you create a website presenting
daily writings, it was created with challenges like Writober or Writever in mind, but
it's not tied to a specific challenge.

Daily Writing mainly turns a bunch of markdown files (one per writing), a configuration
file, and a directory of static files into a static HTML website that can be deployed.

It's quite effective when coupled with solutions like [GitHub
Pages](https://docs.github.com/en/pages), [Cloudflare
Pages](https://developers.cloudflare.com/pages/), [GitLab
Pages](https://docs.gitlab.com/user/project/pages/), etc, as you can edit the markdown
files online or push them through git, and have them get redeployed automatically daily
and upon changes.

We haven't documented how to use those options (yet), but the [author's
website](https://github.com/ewjoachim/writober) can be a
showcase for an example using GitHub.

This approach should also make it very easy to use alongside with a CMS, there are
open-source ones like [Sveltia CMS](https://github.com/sveltia/sveltia-cms), allowing
you to setup a website that is usable with a nicer admin interface and without knowing
about git, or things like that.
