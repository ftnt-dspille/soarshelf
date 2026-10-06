"""code-runner -- execute Python snippets with NO sandbox restrictions.

Unlike the stock ``code-snippet`` connector (which execs at module level -- so a
top-level ``return`` is a SyntaxError -- and restricts builtins so ``open()`` is
unavailable), this connector:

  * wraps the snippet in a function so a top-level ``return`` is valid, and
  * runs it with the full, unrestricted ``__builtins__`` (``open()`` works, so a
    snippet can write a CSV file).

SECURITY: this is, by design, arbitrary-code execution with full filesystem
access running as the integrations user. It exists for trusted, operator-authored
playbooks (e.g. the reconcile-and-report archetype). Do not expose it to
untrusted playbook authors.

Snippet contract:
  * ``params`` -- dict of the operation's ``input`` argument (the playbook passes
    its data here); access values as ``params['recipients']`` etc.
  * ``config`` -- the connector configuration dict.
  * ``return <value>`` -- whatever you return becomes ``code_output`` in the step
    result (``vars.steps.<Step>.data.code_output`` in Jinja). A dict/list is
    returned as-is (JSON-serialisable structures recommended).
"""

import io
import json
import textwrap
import tokenize

from connectors.core.connector import ConnectorError, get_logger

logger = get_logger("code-runner")


def _coerce_input(raw):
    """Normalise the ``input`` param into a dict for the snippet's ``params``."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            loaded = json.loads(raw)
            return loaded if isinstance(loaded, dict) else {"input": loaded}
        except (ValueError, TypeError):
            return {"input": raw}
    return {"input": raw}


def _indent_snippet(code, prefix="    "):
    """Indent each logical line of ``code``, never the interior of a string.

    ``textwrap.indent`` prefixes every physical line, including the lines inside
    a triple-quoted literal -- silently corrupting any multi-line value (a PEM
    interpolated by the playbook arrives with ``prefix`` on every base64 line).
    Tokenize first and leave the continuation rows of multi-line tokens alone.
    """
    lines = code.splitlines(keepends=True)
    interior = set()  # 1-based rows that continue a multi-line token
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.end[0] > tok.start[0]:
                interior.update(range(tok.start[0] + 1, tok.end[0] + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Malformed snippet: fall back -- compile() will report the real error.
        return textwrap.indent(code, prefix)
    out = []
    for row, line in enumerate(lines, start=1):
        if row in interior or not line.strip():
            out.append(line)
        else:
            out.append(prefix + line)
    return "".join(out)


def run_python(config, params):
    """Execute the snippet in ``params['code']`` and return its value as ``code_output``."""
    code = params.get("code") or ""
    if not code.strip():
        raise ConnectorError("No code provided")
    snippet_params = _coerce_input(params.get("input"))

    # Wrap the user code as a function body so a top-level ``return`` is valid.
    body = _indent_snippet(code) or "    pass"
    source = "def __snippet__(params, config):\n" + body
    namespace = {}
    try:
        compiled = compile(source, "<code-runner>", "exec")
        # Full, unrestricted builtins -- open()/import/etc. all available.
        exec(compiled, {"__builtins__": __builtins__}, namespace)  # noqa: S102
        result = namespace["__snippet__"](snippet_params, config)
    except ConnectorError:
        raise
    except SyntaxError as e:
        logger.exception("code-runner snippet has a syntax error")
        raise ConnectorError(f"Snippet syntax error: {e}") from e
    except Exception as e:
        logger.exception("code-runner snippet raised")
        raise ConnectorError(f"Snippet execution failed: {e}") from e
    return {"code_output": result}


def check_health(config):
    """No external dependency -- the connector is healthy if it can run a trivial snippet."""
    out = run_python(config, {"code": "return True"})
    if not out.get("code_output"):
        raise ConnectorError("Health check failed: snippet did not execute")
    return True


operations = {
    "run_python": run_python,
}
