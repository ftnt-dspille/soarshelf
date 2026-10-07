# soarshelf

Community-shared playbooks, solution packs and connectors for SOAR platforms.
Browse by use case or connector, see each playbook as a graph, check what it
needs, and download a cleaned, inactive copy to import.

> Independent community project. Not affiliated with, endorsed by, or
> sponsored by Fortinet. Product names are trademarks of their owners and are
> used only to describe compatibility.

## Layout

| Path | What |
|---|---|
| `content/` | Published items: `<type>/<slug>/meta.yaml` + one cleaned payload. `contributors.yaml` sets trust tiers. |
| `pipeline/` | Python: checks, sanitizer, dependency analysis, site data build. |
| `site/` | SvelteKit static site. Reads only what the pipeline writes to `site/static/data` and `site/static/downloads`. |
| `docs/` | `plan.md` (roadmap, architecture, costs), `data-contract.md` (pipeline → site JSON). |

## Develop

```bash
cd pipeline && uv venv && uv pip install -e '.[test]' && .venv/bin/pytest
cd .. && pipeline/.venv/bin/soarshelf build            # writes site/static/{data,downloads}
pipeline/.venv/bin/soarshelf yaml                      # refresh the readable playbook YAML views in content/
cd site && npm install && npm run dev
```

## Check a file before sharing it

```bash
soarshelf check my-playbook.json                       # report + publish decision
soarshelf check my-playbook.json --meta meta.yaml --clean-out playbook.json
```

`--clean-out` writes exactly what the site would publish. Commit that file,
never the raw export. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Refresh the Content Hub snapshot

```bash
soarshelf hub-index                                    # from the public catalog
soarshelf hub-index --packs-dir /path/to/unpacked/packs   # also rebuild official-content fingerprints
```
