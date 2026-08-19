import pytest

from polyforge.nlu import ollama_client

REAL_SERVER = ollama_client.is_running()
UNUSED_PORT_URL = "http://localhost:18453"  # nothing should ever be listening here


def test_find_ollama_binary_does_not_raise():
    # Either a path string or None -- just must not blow up, on a machine
    # with or without ollama installed.
    result = ollama_client.find_ollama_binary()
    assert result is None or isinstance(result, str)


def test_is_running_false_for_an_unused_port():
    assert ollama_client.is_running(UNUSED_PORT_URL, timeout=1.0) is False


def test_ensure_server_without_auto_start_raises_clearly_when_not_running():
    with pytest.raises(ollama_client.OllamaUnavailable, match="auto_start is off"):
        ollama_client.ensure_server(UNUSED_PORT_URL, auto_start=False)


def test_ensure_server_reports_binary_missing(monkeypatch):
    monkeypatch.setattr(ollama_client, "find_ollama_binary", lambda: None)
    with pytest.raises(ollama_client.OllamaUnavailable, match="isn't installed"):
        ollama_client.ensure_server(UNUSED_PORT_URL, auto_start=True, startup_timeout=1.0)


def test_select_model_picks_first_when_none_requested(monkeypatch):
    fake_models = [
        ollama_client.ModelInfo(name="gemma4:latest"),
        ollama_client.ModelInfo(name="llama3.2:latest"),
    ]
    monkeypatch.setattr(ollama_client, "list_models", lambda base_url, timeout=2.0: fake_models)
    assert ollama_client.select_model("http://irrelevant") == "gemma4:latest"


def test_select_model_matches_ignoring_tag_suffix(monkeypatch):
    fake_models = [ollama_client.ModelInfo(name="llama3.2:latest")]
    monkeypatch.setattr(ollama_client, "list_models", lambda base_url, timeout=2.0: fake_models)
    assert ollama_client.select_model("http://irrelevant", requested="llama3.2") == "llama3.2:latest"


def test_select_model_raises_with_available_list_when_requested_missing(monkeypatch):
    fake_models = [ollama_client.ModelInfo(name="gemma4:latest")]
    monkeypatch.setattr(ollama_client, "list_models", lambda base_url, timeout=2.0: fake_models)
    with pytest.raises(ollama_client.OllamaUnavailable, match="gemma4:latest"):
        ollama_client.select_model("http://irrelevant", requested="mistral")


def test_select_model_raises_when_nothing_installed(monkeypatch):
    monkeypatch.setattr(ollama_client, "list_models", lambda base_url, timeout=2.0: [])
    with pytest.raises(ollama_client.OllamaUnavailable, match="no models installed"):
        ollama_client.select_model("http://irrelevant")


# ---- Against a real, already-running local server (skipped otherwise) ----

@pytest.mark.skipif(not REAL_SERVER, reason="no Ollama server reachable at the default URL")
def test_ensure_server_reports_already_running_against_the_real_server():
    status = ollama_client.ensure_server()
    assert status.running is True
    assert status.started_by_us is False


@pytest.mark.skipif(not REAL_SERVER, reason="no Ollama server reachable at the default URL")
def test_list_models_against_the_real_server_returns_model_info_objects():
    models = ollama_client.list_models()
    assert isinstance(models, list)
    for m in models:
        assert isinstance(m, ollama_client.ModelInfo)
        assert m.name


@pytest.mark.skipif(not REAL_SERVER, reason="no Ollama server reachable at the default URL")
def test_select_model_against_the_real_server_returns_an_installed_name():
    models = ollama_client.list_models()
    if not models:
        pytest.skip("server reachable but no models installed")
    chosen = ollama_client.select_model()
    assert chosen in {m.name for m in models}
