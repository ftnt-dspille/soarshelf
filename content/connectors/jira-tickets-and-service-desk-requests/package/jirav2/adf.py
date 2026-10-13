"""
Copyright start
MIT License
Copyright (c) 2025 Fortinet Inc
Copyright end

Atlassian Document Format helpers.

Jira Cloud REST v3 takes rich text (descriptions, comments) as ADF JSON, not
strings. Playbooks mostly hold plain text, so every text input goes through
to_adf(), and a caller who already has an ADF document can pass it unchanged.
"""
import json


def _text_node(text):
    return {'type': 'text', 'text': text}


def _paragraph(text):
    content = []
    lines = text.split('\n')
    for index, line in enumerate(lines):
        if index:
            content.append({'type': 'hardBreak'})
        if line:
            content.append(_text_node(line))
    return {'type': 'paragraph', 'content': content}


def is_adf(value):
    return isinstance(value, dict) and value.get('type') == 'doc'


def to_adf(value):
    """Return an ADF document for plain text, a JSON string or an ADF dict.

    Blank lines split paragraphs; single newlines become hard breaks.
    """
    if value is None:
        return None
    if is_adf(value):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith('{') and '"doc"' in stripped:
            try:
                parsed = json.loads(stripped)
            except ValueError:
                parsed = None
            if is_adf(parsed):
                return parsed
        text = value.replace('\r\n', '\n').replace('\r', '\n')
        paragraphs = [p for p in text.split('\n\n')] if text.strip() else ['']
        content = [_paragraph(p.strip('\n')) for p in paragraphs]
        return {'type': 'doc', 'version': 1, 'content': content}
    return to_adf(str(value))


def adf_to_text(node):
    """Flatten an ADF node (or a REST v3 body) to plain text."""
    if node is None:
        return ''
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(adf_to_text(child) for child in node)
    if not isinstance(node, dict):
        return str(node)
    kind = node.get('type')
    if kind == 'text':
        return node.get('text', '')
    if kind == 'hardBreak':
        return '\n'
    if kind in ('mention', 'emoji', 'inlineCard'):
        attrs = node.get('attrs') or {}
        return attrs.get('text') or attrs.get('url') or attrs.get('shortName') or ''
    inner = adf_to_text(node.get('content') or [])
    if kind in ('paragraph', 'heading', 'listItem', 'codeBlock', 'blockquote', 'tableRow'):
        return inner + '\n'
    return inner
