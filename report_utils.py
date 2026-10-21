from datetime import datetime, timezone
import re
import json
from pathlib import Path
from threading import Lock
from typing import Dict, Any

# Directory where reports are stored – relative to this file
REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# In‑memory duplicate guard
_processed: Dict[tuple, Dict[str, Any]] = {}
_lock = Lock()

def _make_safe_id(incident_id: str) -> str:
    """Return a filesystem‑safe filename (max 100 chars)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", incident_id)[:100]
    return safe


def update_report(event_data: Dict[str, Any], outputs: Dict[str, Any]) -> str:
    """Create or append to the per‑incident report.

    * If a report for ``event_data["incident_id"]`` does not exist, a new JSON
      file is created with the required top‑level fields and an ``events`` list
      containing the supplied event.
    * If the report exists, the new event dict is appended to ``events`` and
      ``current_status``, ``last_updated_at`` are updated.
    * The file is written atomically (temp‑file + ``os.replace``).
    """
    safe_id = _make_safe_id(event_data["incident_id"]) + ".json"
    report_path = REPORTS_DIR / safe_id

    # Build the event entry – include the original payload fields we care about
    event_entry = {
        "event": event_data.get("event"),
        "status": event_data.get("status"),
        "timestamp": event_data.get("timestamp"),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "outputs": outputs,
    }

    if report_path.is_file():
        # Load existing report and append
        try:
            report = json.loads(report_path.read_text())
        except Exception:
            report = {}
        # Ensure the structure exists
        report.setdefault("events", [])
        report.setdefault("first_received_at", event_entry["received_at"])  # keep original if missing
        report["events"].append(event_entry)
        report["current_status"] = event_data.get("status")
        report["last_updated_at"] = event_entry["received_at"]
        # Update top‑level fields in case they changed (location, etc.)
        for key in ["incident_id", "location", "latitude", "longitude", "severity"]:
            if key in event_data:
                report[key] = event_data[key]
    else:
        # Fresh report – populate required top‑level keys
        report = {
            "incident_id": event_data.get("incident_id"),
            "location": event_data.get("location"),
            "latitude": event_data.get("latitude"),
            "longitude": event_data.get("longitude"),
            "severity": event_data.get("severity"),
            "first_received_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "current_status": event_data.get("status"),
            "events": [event_entry],
        }

    # Write atomically
    tmp_path = report_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    tmp_path.replace(report_path)
    return str(report_path)

    """Write a JSON report file and return its relative path.

    The report is stored as ``reports/<safe_id>.json``.
    """
    safe_id = _make_safe_id(event_data["incident_id"]) + ".json"
    report_path = REPORTS_DIR / safe_id
    report = {
        **event_data,
        "received_at": event_data.get("received_at"),
        "output_status": output_status,
        "report_file": str(report_path.relative_to(Path(__file__).parent)),
    }
    # Write atomically
    tmp_path = report_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    tmp_path.replace(report_path)
    return str(report_path)

def load_report(incident_id: str) -> Dict[str, Any] | None:
    safe_id = _make_safe_id(incident_id) + ".json"
    path = REPORTS_DIR / safe_id
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def list_reports() -> list[Dict[str, Any]]:
    reports = []
    for p in REPORTS_DIR.iterdir():
        if p.suffix != ".json":
            continue
        try:
            data = json.loads(p.read_text())
            reports.append(data)
        except Exception:
            continue
    # newest first (by received_at if present)
    reports.sort(key=lambda r: r.get("received_at", ""), reverse=True)
    return reports

def check_duplicate(incident_id: str, event_type: str) -> tuple[bool, Any]:
    key = (incident_id, event_type)
    with _lock:
        if key in _processed:
            return True, _processed[key]
        return False, None

def mark_processed(incident_id: str, event_type: str, result: Any) -> None:
    key = (incident_id, event_type)
    with _lock:
        _processed[key] = result

def unmark_processed(incident_id: str, event_type: str) -> None:
    key = (incident_id, event_type)
    with _lock:
        _processed.pop(key, None)

