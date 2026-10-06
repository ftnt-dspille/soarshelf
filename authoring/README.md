# Playbook sources

YAML sources for the playbooks the maintainers wrote for the site, in
`fsr_playbooks` YAML. Compile one with
`fsrpb compile <file>.yaml -o out.json`, then add or update the item with
`soarshelf add out.json ...` and test it on a live box with `soarshelf test-live`.

The published copy in `content/` is what the site serves; these are here so a
fix starts from the source.
