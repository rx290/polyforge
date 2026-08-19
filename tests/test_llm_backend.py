import pytest

from polyforge.nlu import llm_backend, ollama_client


def test_match_surfaces_ollama_unavailable_as_llm_backend_unavailable(monkeypatch):
    def raise_unavailable(base_url, auto_start=True):
        raise ollama_client.OllamaUnavailable("no server here")

    monkeypatch.setattr(ollama_client, "ensure_server", raise_unavailable)
    with pytest.raises(llm_backend.LLMBackendUnavailable, match="no server here"):
        llm_backend.match("a wall shelf")


def test_match_never_hardcodes_a_default_model(monkeypatch):
    # ensure_server succeeds; select_model raises because nothing is
    # installed -- match() must surface that, not silently fall back to a
    # hardcoded model name (the old DEFAULT_MODEL = "llama3.2" bug).
    monkeypatch.setattr(ollama_client, "ensure_server", lambda base_url, auto_start=True: None)

    def raise_no_models(base_url, requested=None):
        raise ollama_client.OllamaUnavailable("no models installed")

    monkeypatch.setattr(ollama_client, "select_model", raise_no_models)
    with pytest.raises(llm_backend.LLMBackendUnavailable, match="no models installed"):
        llm_backend.match("a wall shelf")


def test_match_passes_requested_model_through_to_select_model(monkeypatch):
    monkeypatch.setattr(ollama_client, "ensure_server", lambda base_url, auto_start=True: None)
    captured = {}

    def fake_select(base_url, requested=None):
        captured["requested"] = requested
        return "gemma4:latest"

    monkeypatch.setattr(ollama_client, "select_model", fake_select)

    # Now let the actual HTTP call fail fast (nothing listening) so the test
    # doesn't depend on a real model's output -- we're only checking the
    # model-selection plumbing above this point.
    with pytest.raises(llm_backend.LLMBackendUnavailable):
        llm_backend.match("a wall shelf", base_url="http://localhost:18453", model="mistral")
    assert captured["requested"] == "mistral"


@pytest.mark.skipif(not ollama_client.is_running(), reason="no Ollama server reachable at the default URL")
def test_match_end_to_end_against_the_real_server_returns_a_known_template():
    models = ollama_client.list_models()
    if not models:
        pytest.skip("server reachable but no models installed")
    result = llm_backend.match("a plain 60x40x8mm box", timeout=180.0)
    from polyforge import templates
    templates.get(result.template_key)  # raises KeyError if it invented an unknown template
