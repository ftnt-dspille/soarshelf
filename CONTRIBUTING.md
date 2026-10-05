# Contributing

In-browser uploads are coming. Until then, contribute with a pull request.

## 1. Export

- **Playbooks:** export the collection from the platform as JSON.
- **Solution packs:** export as a solution pack zip. Configuration exports are
  not accepted: they can carry environment data. Packs must not bundle
  connector or widget installers; list those separately.
- **Connectors:** we list the manifest (`info.json`) and link to your public
  source repository. We don't host connector code.

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
