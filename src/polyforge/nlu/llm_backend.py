"""Optional local-model-backed engine for freer-form request text.

Still bounded to the same template vocabulary as template_matcher — the model's
job is only smarter slot-filling for casually phrased requests, not writing
arbitrary novel OpenSCAD. Talks to an Ollama-compatible local server by default
(nothing leaves the machine); point POLYFORGE_LLM_URL at any OpenAI- or
Ollama-compatible endpoint to use a different local runtime.
"""

from __future__ import annotations

import json
import os
import urllib.request

from .. import templates
from .template_matcher import MatchResult

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class LLMBackendUnavailable(Exception):
    """Raised when the local model can't be reached or returns unusable output."""


def _templates_prompt() -> str:
    lines = []
    for t in templates.all_templates():
        params = ", ".join(f"{p.name} (default {p.default}{p.unit}) - {p.description}" for p in t.params)
        lines.append(f"- key={t.key}: {t.description}\n  params: {params}")
    return "\n".join(lines)


def _build_prompt(text: str) -> str:
    return (
        "You select exactly one part template and fill in only the parameters the "
        "user's request implies; leave the rest out so defaults apply.\n"
        "Respond with ONLY strict JSON of the shape "
        '{\"template\": \"<key>\", \"params\": {\"<name>\": <number>, ...}}. '
        "No prose, no markdown fences, no explanation.\n\n"
        f"Available templates:\n{_templates_prompt()}\n\n"
        f"User request: {text}"
    )


def match(
    text: str,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 30.0,
) -> MatchResult:
    base_url = base_url or os.environ.get("POLYFORGE_LLM_URL", DEFAULT_BASE_URL)
    model = model or os.environ.get("POLYFORGE_LLM_MODEL", DEFAULT_MODEL)
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
            f"Could not reach a local model at {base_url} (model={model}): {exc}. "
            "Start it (e.g. `ollama serve` + `ollama pull llama3.2`), set POLYFORGE_LLM_URL/"
            "POLYFORGE_LLM_MODEL to point elsewhere, or use --engine templates instead."
        ) from exc

    raw = body.get("response", "")
    try:
        parsed = json.loads(raw)
        template_key = parsed["template"]
        params = parsed.get("params", {})
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LLMBackendUnavailable(f"Local model returned unusable output: {raw!r}") from exc

    try:
        templates.get(template_key)
    except KeyError as exc:
        raise LLMBackendUnavailable(str(exc)) from exc

    return MatchResult(template_key=template_key, confidence=0.6, params=params, notes=[f"local model {model} @ {base_url}"])
