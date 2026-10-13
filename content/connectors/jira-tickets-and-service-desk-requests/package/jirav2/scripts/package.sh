#!/usr/bin/env bash
# Build the connector bundle FortiSOAR installs.
#
# The tarball must unpack to a single `jirav2/` directory holding the
# git-tracked files minus the development-only ones below. Packaging the
# working directory instead is how a small bundle becomes 14 MB: `.venv/`
# gets swept in.
set -euo pipefail

cd "$(dirname "$0")/.."
NAME=$(python3 -c "import json;print(json.load(open('info.json'))['name'])")
VERSION=$(python3 -c "import json;print(json.load(open('info.json'))['version'])")
OUT="dist/${NAME}-${VERSION}.tgz"

# Never shipped: tests, generators, docs and repo furniture. The appliance
# neither needs nor runs any of it.
EXCLUDE='^(\.github/|\.gitignore$|README\.md$|scripts/|tests/|dist/|playbooks/.*\.yaml$)'

FILES=()
while IFS= read -r f; do FILES+=("$f"); done < <(git ls-files | grep -Ev "$EXCLUDE")
if [ ${#FILES[@]} -eq 0 ]; then
    echo "package: no files matched - run from a git checkout" >&2
    exit 1
fi

for required in info.json connector.py operations.py client.py scope_data.py; do
    printf '%s\n' "${FILES[@]}" | grep -qx "$required" \
        || { echo "package: $required missing from the bundle (git add it?)" >&2; exit 1; }
done

rm -rf dist && mkdir -p "dist/stage/${NAME}"
# Staged and copied rather than tarred with a prefix option: GNU tar spells
# that --transform and bsdtar spells it -s, so a script using either breaks
# on the other.
for f in "${FILES[@]}"; do
    mkdir -p "dist/stage/${NAME}/$(dirname "$f")"
    cp "$f" "dist/stage/${NAME}/$f"
done
tar czf "$OUT" -C dist/stage "${NAME}"
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
