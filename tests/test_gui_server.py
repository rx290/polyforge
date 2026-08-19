import json
import threading
import urllib.error
import urllib.request

import pytest

from polyforge.gui import server as gui_server


@pytest.fixture
def running_server(tmp_path):
    httpd = gui_server.make_server(tmp_path, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base_url
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _get_raw(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read()


def _post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_index_page_served(running_server):
    status, body = _get_raw(f"{running_server}/")
    assert status == 200
    assert b"PolyForge" in body


def test_templates_endpoint(running_server):
    status, body = _get(f"{running_server}/api/templates")
    assert status == 200
    assert any(t["key"] == "box" for t in body)


def test_ollama_status_endpoint_always_returns_200(running_server):
    status, body = _get(f"{running_server}/api/ollama/status")
    assert status == 200
    assert "reachable" in body


def test_design_then_download_round_trip(running_server):
    status, body = _post(f"{running_server}/api/design", {"text": "a box", "set": {"width": "77"}})
    assert status == 200
    assert body["params"]["width"] == 77.0

    status, raw = _get_raw(f"{running_server}/files/{body['filename']}")
    assert status == 200
    assert b"width = 77" in raw


def test_design_bad_request_returns_400_not_a_stack_trace(running_server):
    status, body = _post(f"{running_server}/api/design", {"text": "  "})
    assert status == 400
    assert "error" in body


def test_files_path_traversal_is_rejected(running_server):
    status, body = _get(f"{running_server}/files/../../../../etc/passwd")
    assert status == 403
