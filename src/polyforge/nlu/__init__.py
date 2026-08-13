"""Two selectable engines that turn request text into a (template, params) match:

- template_matcher: zero-ML keyword/regex matching. Default, always available.
- llm_backend: optional, calls a local model (e.g. Ollama) for freer phrasing.
"""
