#!/usr/bin/env bash
# Local stand-in for .github/workflows/submission.yml's `check` job:
# fetch a quarantined upload from a local Worker, run the pipeline against a
# scratch copy of content/, and post the result back. No git, no PR.
#
#   scripts/simulate-submission.sh <submission-id> [api-base]
set -euo pipefail
ID="$1"
API="${2:-http://127.0.0.1:8787}/api/internal/submissions"
[[ "$ID" =~ ^[0-9a-f]{32}$ ]] || { echo "invalid id"; exit 1; }
TOKEN=$(grep '^INTERNAL_TOKEN=' "$(dirname "$0")/../worker/.dev.vars" | cut -d= -f2-)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

curl -fsS -H "Authorization: Bearer $TOKEN" "$API/$ID" -o "$WORK/info.json"
login=$(jq -r .login "$WORK/info.json")
uid=$(jq -r .githubId "$WORK/info.json")
case "$(jq -r .filename "$WORK/info.json")" in *.json) ext=json ;; *.zip) ext=zip ;; *) exit 1 ;; esac
jq .meta "$WORK/info.json" > "$WORK/meta.json"
curl -fsS -H "Authorization: Bearer $TOKEN" "$API/$ID/file" -o "$WORK/upload.$ext"

cp -R "$ROOT/content" "$WORK/content"
"$ROOT/pipeline/.venv/bin/soarshelf" intake-submission --file "$WORK/upload.$ext" --meta "$WORK/meta.json" \
  --author "$login" --author-id "$uid" --content "$WORK/content" --report "$WORK/report.json"

decision=$(jq -r .decision "$WORK/report.json")
status=$([ "$decision" = reject ] && echo rejected || echo in-review)
jq --arg status "$status" '{status: $status, decision, reasons, checks, slug, strike}' "$WORK/report.json" \
  | curl -fsS -X POST -H "Authorization: Bearer $TOKEN" -H "content-type: application/json" \
      --data-binary @- "$API/$ID/result"
echo
echo "$ID -> $status ($decision)"
