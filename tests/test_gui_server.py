import json
import threading
import time
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


def _poll_job(base_url, job_id, timeout=60):
    """Poll a background job to completion, asserting the progress payload
    shape on every tick along the way (this is what the GUI's progress bar
    is driven by, so a malformed shape here would silently break it)."""
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        status, job = _get(f"{base_url}/api/jobs/{job_id}")
        assert status == 200
        assert job["progress"].keys() >= {"done", "total", "label"}
        if job["status"] != "running":
            return job
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s: {job}")


def test_unknown_job_id_returns_404(running_server):
    status, body = _get(f"{running_server}/api/jobs/does-not-exist")
    assert status == 404


def test_preview_starts_a_pollable_background_job(running_server):
    """/api/preview must return immediately with a job id (not block the
    request for the full multi-view render), so the GUI can poll progress
    instead of just staring at a spinner with no feedback."""
    status, body = _post(f"{running_server}/api/design", {"text": "a box"})
    assert status == 200
    filename = body["filename"]

    status, body = _post(f"{running_server}/api/preview", {"filename": filename})
    assert status == 202
    assert body["job_id"]

    job = _poll_job(running_server, body["job_id"])
    # Whether or not openscad is installed on this machine, the job must
    # resolve cleanly either way -- and if it succeeds, all 7 views ran.
    assert job["status"] in ("done", "error")
    if job["status"] == "done":
        assert len(job["result"]["views"]) == 7
        assert job["progress"]["done"] == job["progress"]["total"] == 7
