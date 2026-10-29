# Hand-sourced connector icons

Icons for connectors the automation can't cover: platform built-ins with no
package of their own, and community packages whose icon is a placeholder.
These are curated by hand, committed here, and they win over everything else
(a connector's own package icon, and the Content Hub fetch in `../icons/`).

`soarshelf hub-icons` never writes to or prunes this directory; a file here is
a standing maintainer decision, not a snapshot artifact. Add a file named
`<connector-machine-name>.png` (re-drawn, at most 96px — `_clean_icon` does
this) and it is served for every item that connector appears on.

| File | For | Source |
|---|---|---|
| `ansible-automation.png` | Ansible Automation connector | [Ansible logo](https://commons.wikimedia.org/wiki/File:Ansible_Logo.png) (Wikimedia Commons) |
| `code-runner.png` | Code Runner built-in connector | [Python logo, no text](https://commons.wikimedia.org/wiki/File:Python-logo-notext.svg) (Wikimedia Commons) |

Product logos identify the products they belong to; they remain the property
of their respective owners.
