#!/usr/bin/env python3
"""Create the scoped API tokens the online scope tests need, by driving Atlassian's token form.

Atlassian has no API for creating tokens, so this fills the same form you would, in a
browser window it opens. It cannot sign in for you: log in (and pass the one-time
passcode check Atlassian asks for before showing API tokens) in that window, and the
script carries on by itself once the "API Tokens" page is up.

    uv run --with playwright python scripts/make_scope_tokens.py --plan          # show, do nothing
    uv run --with playwright python scripts/make_scope_tokens.py                  # granular plan
    uv run --with playwright python scripts/make_scope_tokens.py --family classic
    uv run --with playwright python scripts/make_scope_tokens.py --only health

Each token is named `jirav2-test-<family>-<name>`, expires in 7 days (the form's default),
and is written to tests/scope_tokens.json (mode 600, git-ignored) together with the
scopes it was asked for. The token itself is never printed. Afterwards the script opens
"View scopes" for each new token and fails loudly if the form did not keep every scope.
Revoke them on the same page when you are done.

Needs Playwright's Chromium: `uv run --with playwright playwright install chromium`.
"""
import argparse
import json
import os
import re
import sys
import types

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
_package = types.ModuleType('jirav2')
_package.__path__ = [ROOT]
sys.modules['jirav2'] = _package

from jirav2.scopes import pack_tokens  # noqa: E402

TOKENS_PAGE = 'https://id.atlassian.com/manage-profile/security/api-tokens'
TOKEN_RE = re.compile(r'ATATT[A-Za-z0-9_\-=]{60,}')
TOKENS_FILE = os.path.join(ROOT, 'tests', 'scope_tokens.json')
PROFILE_DIR = os.path.join(ROOT, 'tests', '.playwright-profile')
SHOTS = os.environ.get('SCOPE_TOKEN_SHOTS', os.path.join(ROOT, 'tests', '.playwright-profile', 'shots'))
LOGIN_WAIT_MS = 15 * 60 * 1000


def plan(args):
    tokens = pack_tokens(args.family)
    if args.only:
        tokens = [t for t in tokens if t['name'] in args.only]
    return tokens


def read_token(page):
    """Find the freshly minted token on the page (inputs first, then visible text)."""
    candidates = page.eval_on_selector_all(
        'input, textarea', 'els => els.map(e => e.value || "")')
    candidates.append(page.inner_text('body'))
    for text in candidates:
        found = TOKEN_RE.search(text or '')
        if found:
            return found.group(0)
    return None


def shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, name + '.png')
    page.screenshot(path=path)
    return path


def fill_wizard(page, title, scopes):
    page.get_by_role('button', name='Create API token with scopes').click()
    page.get_by_label(re.compile(r'^Name')).fill(title)
    page.get_by_role('button', name='Next').click()
    page.get_by_role('radio', name='Jira', exact=True).check()
    page.get_by_role('button', name='Next').click()
    search = page.get_by_placeholder('Search by scope name')
    search.wait_for()
    for scope in scopes:
        search.fill(scope)
        cell = page.get_by_role('cell', name=scope, exact=True)
        cell.first.wait_for(timeout=15000)
        row = page.get_by_role('row').filter(has=cell)
        box = row.first.get_by_role('checkbox')
        box.check()
        if not box.is_checked():
            raise RuntimeError('could not tick %s' % scope)
    page.get_by_role('button', name='Next').click()


def create_token(page, title, scopes):
    fill_wizard(page, title, scopes)
    # The last step may ask for a final confirmation before it shows the token.
    for label in ('Create', 'Create token', 'Create API token'):
        button = page.get_by_role('button', name=label, exact=True)
        if button.count() and button.first.is_visible():
            button.first.click()
            break
    for _ in range(30):
        token = read_token(page)
        if token:
            return token
        page.wait_for_timeout(500)
    raise RuntimeError('the new token never appeared (see screenshot %s)' % shot(page, 'no-token-' + title))


def close_dialog(page):
    for label in ('Close', 'Done'):
        button = page.get_by_role('button', name=label, exact=True)
        if button.count() and button.first.is_visible():
            button.first.click()
            return
    page.goto(TOKENS_PAGE)


def verify_scopes(page, title, scopes):
    """Open View scopes for the token and compare against what was asked for."""
    page.goto(TOKENS_PAGE)
    page.get_by_role('button', name='Create API token with scopes').wait_for(timeout=60000)
    row = page.get_by_role('row').filter(has_text=title)
    row.get_by_text('View scopes').first.click()
    page.wait_for_timeout(1500)
    text = page.inner_text('body')
    missing = [s for s in scopes if s not in text]
    if missing:
        raise RuntimeError('token %s is missing scopes after creation: %s (screenshot %s)'
                           % (title, missing, shot(page, 'verify-' + title)))
    close_dialog(page)


def save(entry):
    existing = []
    if os.path.exists(TOKENS_FILE):
        existing = json.load(open(TOKENS_FILE))
    existing = [e for e in existing if e['name'] != entry['name']]
    existing.append(entry)
    with open(TOKENS_FILE, 'w') as handle:
        json.dump(existing, handle, indent=2)
        handle.write('\n')
    os.chmod(TOKENS_FILE, 0o600)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--family', choices=('granular', 'classic'), default='granular')
    ap.add_argument('--only', nargs='*', help='token names from the plan (health, pack-1, ...)')
    ap.add_argument('--plan', action='store_true', help='show the plan and exit')
    args = ap.parse_args()
    tokens = plan(args)
    for token in tokens:
        print('%-8s %2d scopes, %2d actions' % (token['name'], len(token['scopes']), len(token['actions'])))
    if args.plan:
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, viewport={'width': 1280, 'height': 900})
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(TOKENS_PAGE)
        print('If asked, sign in and pass the passcode check in the browser window. Waiting for the API Tokens page...')
        page.get_by_role('button', name='Create API token with scopes').wait_for(timeout=LOGIN_WAIT_MS)
        for token in tokens:
            title = 'jirav2-test-%s-%s' % (args.family, token['name'])
            try:
                secret = create_token(page, title, token['scopes'])
            except Exception as err:
                print('FAILED %s: %s' % (title, err))
                shot(page, 'failed-' + title)
                context.close()
                sys.exit(1)
            save({'name': token['name'] if args.family == 'granular' else 'classic-' + token['name'],
                  'family': args.family, 'scopes': token['scopes'], 'token': secret})
            print('created %s (%d scopes)' % (title, len(token['scopes'])))
            close_dialog(page)
            verify_scopes(page, title, token['scopes'])
            print('verified %s' % title)
        context.close()


if __name__ == '__main__':
    main()
