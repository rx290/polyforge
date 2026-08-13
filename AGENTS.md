# Using PolyForge from any agent or LLM

There is no shared skill/plugin format across Claude, ChatGPT, Gemini, Kimi K2, and
local models — Claude Code has `SKILL.md`, OpenAI products have `agents/openai.yaml`,
and everything else has nothing standard. Chasing every platform's proprietary format
isn't the fix. Instead, PolyForge's actual capability is a **standalone CLI that needs
no agent at all** (`src/polyforge/`, installed as the `polyforge` command). Every
platform below just needs to be told to call it.

## Claude Code

Native support — drop `.claude/skills/polyforge/` into your skills directory. See the
main [README](README.md#install).

## ChatGPT / Codex

Native support via `.claude/skills/polyforge/agents/openai.yaml`.

## Gemini, Kimi K2, or any tool-calling-capable model (cloud or local)

Register `polyforge design "<text>"` as a function/tool the model can call. A minimal
JSON tool schema:

```json
{
  "name": "polyforge_design",
  "description": "Generate a parametric OpenSCAD (.scad) file for a common 3D-printable part (box/enclosure, wall shelf, corner bracket, cable comb, standoff mount plate) from a natural-language description.",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {"type": "string", "description": "What to build, e.g. 'a wall shelf 200x150x5mm with 2 M4 holes'"},
      "engine": {"type": "string", "enum": ["templates", "llm"], "default": "templates"}
    },
    "required": ["text"]
  }
}
```

Wire the call to `subprocess.run(["polyforge", "design", text, "--engine", engine, "--out", out_path])`
and return the written `.scad` path (and its contents, if the model needs to read them
back). The same pattern works for `preview`, `export`, `inspect`, and `repair` — see
`polyforge --help` for their arguments.

## No agent at all

Run it yourself:

```bash
pip install -e .
polyforge design "a shelf 200x150x5mm with 2 M4 holes"
```

Nothing here calls out to a network LLM. The default `templates` engine is pure
Python/regex; `--engine llm` talks to a local model server (Ollama by default) and
still fails closed with a clear error if that server isn't reachable.

## Giving a bare LLM the full authoring rules (no tool-calling)

For a model that can generate OpenSCAD text but has no tool-calling and no template
library to fall back on, paste the contents of
[`.claude/skills/polyforge/SKILL.md`](.claude/skills/polyforge/SKILL.md) into its system
prompt / custom instructions. It documents the authoring rules, dimension discipline,
and printer-aware checks independent of any specific runtime.
