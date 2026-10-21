import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import os
import json
import builtins
from pathlib import Path
from unittest import mock

import pytest

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import sms as sms_mod
from mqtt_worker import post_event
from report_utils import update_report, check_duplicate, mark_processed, unmark_processed, REPORTS_DIR

# Helper to create a minimal IncidentEvent model dict
def make_event(incident_id="INC001", event_type="INCIDENT_CONFIRMED", status="CONFIRMED", location="Loc", latitude=0.0, longitude=0.0, severity="HIGH"):
    return {
        "incident_id": incident_id,
        "event": event_type,
        "status": status,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "severity": severity,
        "timestamp": "2023-01-01T00:00:00Z",
    }

@pytest.fixture(autouse=True)
def isolate_reports(tmp_path, monkeypatch):
    # Point the REPORTS_DIR constant to a temporary directory for the duration of the test
    temp_dir = tmp_path / "reports"
    temp_dir.mkdir(exist_ok=True)
    monkeypatch.setattr('report_utils.REPORTS_DIR', temp_dir, raising=False)
    yield
    # Cleanup in‑memory duplicate guard
    for key in list(mark_processed.__globals__['_processed'].keys()):
        unmark_processed(*key)

def test_sms_disabled(monkeypatch):
    monkeypatch.setenv('ENABLE_SMS', 'false')
    monkeypatch.setenv('DEMO_MODE', 'false')
    result = sms_mod.send_sms('inc1', 'loc')
    assert result == {"status": "disabled"}

def test_sms_simulated(monkeypatch):
    monkeypatch.setenv('ENABLE_SMS', 'true')
    monkeypatch.setenv('DEMO_MODE', 'true')
    result = sms_mod.send_sms('inc1', 'loc')
    assert result == {"status": "simulated"}

def test_sms_missing_config(monkeypatch):
    monkeypatch.setenv('ENABLE_SMS', 'true')
    monkeypatch.setenv('DEMO_MODE', 'false')
    monkeypatch.delenv('MSG91_AUTHKEY', raising=False)
    monkeypatch.delenv('MSG91_TEMPLATE_ID', raising=False)
    monkeypatch.delenv('SMS_RECIPIENTS', raising=False)
    result = sms_mod.send_sms('inc1', 'loc')
    assert result["status"] == "failed"
    assert "Configure MSG91" in result["error"]

@mock.patch('requests.post')
def test_sms_successful_and_invalid_number(mock_post, monkeypatch):
    # Mock a successful provider response
    mock_resp = mock.Mock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.text = "provider ok"
    mock_post.return_value = mock_resp

    monkeypatch.setenv('ENABLE_SMS', 'true')
    monkeypatch.setenv('DEMO_MODE', 'false')
    monkeypatch.setenv('MSG91_AUTHKEY', 'key')
    monkeypatch.setenv('MSG91_TEMPLATE_ID', 'tmpl')
    # One good number, one bad format
    monkeypatch.setenv('SMS_RECIPIENTS', '919876543210,invalid123')

    result = sms_mod.send_sms('inc1', 'loc')
    assert result["status"] == "completed"
    # Two result entries expected
    assert len(result["results"]) == 2
    good, bad = result["results"]
    assert good["status"] == "accepted_by_provider"
    assert good["http_status"] == 200
    assert bad["status"] == "failed"
    assert "Expected Indian number format" in bad["error"]

def test_report_creation_and_append(monkeypatch):
    event1 = make_event()
    outputs1 = {"sign": {"a": 1}, "sms": {"b": 2}, "status_publish": {"c": 3}}
    path1 = update_report(event1, outputs1)
    # Report file should exist
    assert Path(path1).exists()
    data = json.loads(Path(path1).read_text())
    assert data["incident_id"] == event1["incident_id"]
    assert data["current_status"] == event1["status"]
    assert len(data["events"]) == 1
    # Append a CLEARED event
    event2 = make_event(event_type="INCIDENT_CLEARED", status="CLEARED")
    outputs2 = {"sign": {"x": 9}}
    path2 = update_report(event2, outputs2)
    assert path1 == path2
    data2 = json.loads(Path(path2).read_text())
    assert data2["current_status"] == "CLEARED"
    assert len(data2["events"]) == 2
    # Ensure both event entries are present
    assert data2["events"][0]["status"] == "CONFIRMED"
    assert data2["events"][1]["status"] == "CLEARED"

def test_duplicate_guard(monkeypatch):
    incident = "DUP001"
    event_type = "INCIDENT_CONFIRMED"
    # Initially not duplicate
    dup, _ = check_duplicate(incident, event_type)
    assert not dup
    # Mark processed
    mark_processed(incident, event_type, {"dummy": True})
    dup2, cached = check_duplicate(incident, event_type)
    assert dup2
    assert cached == {"dummy": True}
    # Cleanup
    unmark_processed(incident, event_type)
    dup3, _ = check_duplicate(incident, event_type)
    assert not dup3

@mock.patch('requests.post')
def test_mqtt_worker_api_key_header(mock_post, monkeypatch):
    # Mock successful post
    mock_resp = mock.Mock()
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_post.return_value = mock_resp

    monkeypatch.setenv('INTERNAL_API_KEY', 'secret123')
    event = {"incident_id": "X", "event": "INCIDENT_CONFIRMED", "status": "CONFIRMED"}
    success = post_event(event)
    assert success
    # Verify that X‑API‑Key header was sent
    args, kwargs = mock_post.call_args
    headers = kwargs.get('headers', {})
    assert headers.get('X-API-Key') == 'secret123'
