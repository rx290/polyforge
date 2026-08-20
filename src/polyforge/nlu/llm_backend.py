"""Optional local-model-backed engine for freer-form request text.

Still bounded to the same template vocabulary as template_matcher: the model's
job is only smarter slot-filling for casually phrased requests, not writing
arbitrary novel OpenSCAD. Talks to an Ollama-compatible local server by default
(nothing leaves the machine); point POLYFORGE_LLM_URL at any OpenAI- or
Ollama-compatible endpoint to use a different local runtime.

Model/server handling goes through `ollama_client`: no hardcoded model name
(the previous fixed `DEFAULT_MODEL = "llama3.2"` would just fail outright on
a machine that never pulled that exact model), the server is health-checked
and started automatically if it's just not running yet, and connection
failures come back as one clear, actionable error instead of a raw socket
exception.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import urllib.request

from .. import templates
from . import ollama_client
from .ollama_client import OllamaUnavailable
from .template_matcher import MatchResult

DEFAULT_BASE_URL = ollama_client.DEFAULT_BASE_URL


class LLMBackendUnavailable(Exception):
    """Raised when the local model can't be reached or returns unusable output."""


def _templates_prompt() -> str:
    lines = []
    for t in templates.all_templates():
        params = ", ".join(f"{p.name} (default {p.default}{p.unit}) - {p.description}" for p in t.params)
        lines.append(f'- "{t.key}": {t.description}\n  params: {params}')
    return "\n".join(lines)


def _build_prompt(text: str) -> str:
    return (
        "You select exactly one part template and fill in only the parameters the "
        "user's request implies; leave the rest out so defaults apply.\n"
        "Respond with ONLY strict JSON of the shape "
        '{\"template\": \"<key>\", \"params\": {\"<name>\": <number>, ...}}. '
        'The \"<key>\" value must be copied verbatim from one of the quoted template '
        "names below (just the name, e.g. \"vase\" -- never a label like \"key=vase\").\n"
        "No prose, no markdown fences, no explanation.\n\n"
        f"Available templates:\n{_templates_prompt()}\n\n"
        "Example response for a request that matches the vase template:\n"
        '{\"template\": \"vase\", \"params\": {\"vase_height\": 200}}\n\n'
        f"User request: {text}"
    )


def _clean_template_key(raw: str) -> str:
    """Small local models sometimes echo the prompt's own formatting back
    instead of just the bare key (e.g. 'key=vase' or '\"vase\",' or a
    trailing sentence) -- strip that noise before giving up on a response
    that actually did pick the right template."""
    cleaned = raw.strip().strip("'\"")
    cleaned = re.sub(r"^\s*(template\s*=|template\s*:|key\s*=)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip("'\"")
    return cleaned.split()[0].rstrip(".,;:") if cleaned.split() else cleaned


def _resolve_template_key(raw: str) -> str:
    known = [t.key for t in templates.all_templates()]
    candidate = _clean_template_key(raw)
    if candidate in known:
        return candidate
    # last resort: the model named something close to a real key (typo,
    # extra punctuation, wrong casing) -- try a fuzzy match before failing.
    close = difflib.get_close_matches(candidate.lower(), known, n=1, cutoff=0.6)
    if close:
        return close[0]
    raise KeyError(f"unknown template: {raw!r}. Known: {known}")


DEFAULT_GENERATE_TIMEOUT_S = 180.0  # a real local model, especially a "thinking" one, can take
                                     # well over a minute -- confirmed live (~85s for gemma4 on
                                     # this machine's hardware) -- 30s was cutting it off early.


def match(
    text: str,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = DEFAULT_GENERATE_TIMEOUT_S,
    auto_start: bool = True,
) -> MatchResult:
    base_url = base_url or os.environ.get("POLYFORGE_LLM_URL", DEFAULT_BASE_URL)
    requested_model = model or os.environ.get("POLYFORGE_LLM_MODEL")

    try:
        ollama_client.ensure_server(base_url, auto_start=auto_start)
        model = ollama_client.select_model(base_url, requested=requested_model)
    except OllamaUnavailable as exc:
        raise LLMBackendUnavailable(str(exc)) from exc

    prompt = _build_prompt(text)
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any transport/parse failure means "unavailable"
        raise LLMBackendUnavailable(
            f"Ollama at {base_url} was reachable but the generate request failed "
            f"(model={model}): {exc}. Set POLYFORGE_LLM_URL to point elsewhere, or use "
            "--engine templates instead."
        ) from exc

    raw = body.get("response", "")
    # Small local models frequently wrap the JSON in a markdown fence or add
    # a stray sentence before/after it despite being told not to -- pull out
    # the first {...} object rather than requiring the whole response to be
    # pure JSON.
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    candidate_json = json_match.group(0) if json_match else raw
    try:
        parsed = json.loads(candidate_json)
        template_key = parsed["template"]
        params = parsed.get("params", {})
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LLMBackendUnavailable(f"Local model returned unusable output: {raw!r}") from exc

    try:
        template_key = _resolve_template_key(template_key)
    except KeyError as exc:
        raise LLMBackendUnavailable(str(exc)) from exc

    params = params if isinstance(params, dict) else {}
    return MatchResult(template_key=template_key, confidence=0.6, params=params, notes=[f"local model {model} @ {base_url}"])
