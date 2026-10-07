# Contributing

The easiest way is the upload page (`/submit` on the site): drop the file, pick a use case, submit. You can also open a pull request as below.

## 1. Export

- **Playbooks:** export the collection from the platform as JSON.
- **Solution packs:** export as a solution pack zip. Configuration exports are
  not accepted: they can carry environment data. Packs must not bundle
  connector or widget installers; list those separately. Content Hub
  connectors your playbooks use are declared in the pack for you, so
  installing it installs them.
- **Connectors and widgets:** upload the `.tgz` you install on your platform.
  A maintainer reviews the source, and the download is rebuilt from it. No
  compiled code or bundled archives: list Python dependencies in
  `requirements.txt`. Images in the package (e.g. `images/`) become screenshots.

## 2. Check and clean

```bash
pip install ./pipeline
soarshelf check export.json --meta meta.yaml --clean-out playbook.json
```

Fix anything marked `✗`. Commit the file written by `--clean-out`, **never the
raw export**. This repository is public, and a raw export can contain
environment details.

## 3. Add the item

```
content/playbooks/<slug>/
  meta.yaml
  playbook.json         # the cleaned file
```

```yaml
title: Set alert severity from reputation score     # what it does, not a product name
summary: One line, up to 160 characters.
description: |
  Markdown. Explain what it does, what to tune, and where to get any
  connector that isn't on the Content Hub.
use_cases: [enrichment, triage]     # see pipeline/src/soarshelf/config.py USE_CASES
tags: [ip, reputation]
author: your-github-handle
author_id: 12345678        # your numeric GitHub id: gh api users/<handle> --jq .id
version: 1.0.0
min_version: 7.4.0
license: MIT
published: 2026-10-05
# connectors only:
# source: https://github.com/you/your-connector
```

Or let `soarshelf add` do steps 2 and 3. It runs the same checks as the
upload page and writes the folder, crediting your `gh` login:

```bash
soarshelf add export.json --title "..." --summary "..." --use-case triage
soarshelf add https://github.com/you/your-connector --use-case utility      # packages the repo
soarshelf add https://github.com/you/kit/tree/main/widgets/x --use-case reporting
```

Add `--dry-run` to see the report without writing anything.

Playbooks and solution packs also carry a readable YAML view next to the JSON
(`playbook.yaml`, or `playbooks/<collection>/<playbook>.yaml` in a pack): the
playbook as `fsr-playbooks` authoring YAML, one block per step with its connector,
arguments and where it goes next, minus canvas positions and uuids. Reviewers read
that instead of the export. It is generated, not edited, and the JSON stays the
source of truth. `soarshelf add` and the upload pipeline write it, and
`soarshelf yaml` refreshes it. CI fails if one is out of date
(`soarshelf yaml --check`). Run it from the pipeline venv: the views are generated
with the exact `fsr-playbooks` release pinned in `pipeline/pyproject.toml`.

## Updating your item

Upload the new version on the upload page, the same way as the first time.
If it's the same playbook, pack, connector or widget (matched by its playbooks'
ids and steps, or by the connector/widget manifest `name`) and you uploaded the
original, it replaces your item in place: same page and link, a higher version,
and a changelog entry from "What changed". Updates go through the same checks
and review as new items. Items a maintainer added for you are updated by a
maintainer.

## Rules

- Share only what you have the rights to share. No re-uploads of official
  Content Hub content: link to it instead.
- No credentials, internal IPs or hostnames, real email addresses, customer
  names or ticket numbers.
- Don't describe your item as official, certified or endorsed by any vendor.
- Content is published under the MIT licence.

## Review

| Your tier | What happens |
|---|---|
| new | A maintainer reviews every submission. |
| contributor (3 approved, no strikes) | Auto-published when there are no warnings. |
| trusted | Auto-published unless there are secret, environment or provenance warnings. |

Connectors and anything with code steps are always reviewed.
