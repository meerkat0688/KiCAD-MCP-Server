"""Validate document coverage, arithmetic, links, and run the offline model.

Writes only an honest engineering-check record, never product acceptance PASS.
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
requirements = (root/"requirements.md").read_text()
ids = set(re.findall(r"^\| ((?:SEN|MSG|HW|OPS|REL)-\d+) \|", requirements, re.M))
with (root/"traceability.csv").open(encoding="utf-8-sig", newline="") as f:
    trace = list(csv.DictReader(f))
assert len(ids) == len(trace) == 23
assert ids == {r["requirement_id"] for r in trace}
assert all(r["execution_status"] in ("NOT RUN", "N/A") for r in trace)
assert all(r["execution_status"] == "NOT RUN" for r in trace if r["requirement_id"] != "SEN-08")
profile = json.loads((root/"design-profile.json").read_text())
assert profile["user_inputs"]["bin_height_cm"] == 130
assert profile["user_inputs"]["width_cm"] == 70
assert profile["user_inputs"]["lid"] is False
assert profile["known_module_subtotal_usd"] == 4.90+22.95
assert profile["module_prototype_estimate_usd"] == 27.85+16
assert profile["planned_hardware_usd"] is None  # Added carrier cost is unquoted.
assert profile["inventory"] == {"controller_owned":False,"sensor_owned":False}
assert profile["product_accepted"] is False
assert profile["custom_pcb_created"]
assert profile["erc"] == profile["drc"] == "PASS_STATIC"
checks=json.loads((root/"kicad/review/validation.json").read_text())
assert all(checks[k]==0 for k in ['erc_violations','drc_violations','unconnected_items','schematic_parity_issues'])
for name,digest in checks['sha256'].items():
    assert hashlib.sha256((root/'kicad'/name).read_bytes()).hexdigest()==digest, name
with (root/"geometry.csv").open(encoding="utf-8-sig", newline="") as f:
    geometry = {int(r["fill_height_pct"]): float(r["distance_mm"]) for r in csv.DictReader(f)}
assert geometry[80] == 260 and geometry[50] == 650
assert geometry[20] == 1040 and geometry[90] == 130
for name in ("system-overview.svg", "prototype-wiring.svg", "bin-geometry.svg"):
    ET.parse(root/name)
for path in root.rglob("*.md"):
    if path.name == "requirements.md":
        continue  # Unmodified source may contain external reference prose.
    for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if not link.startswith(("http:", "https:", "#")):
            assert (path.parent/link.split("#")[0]).exists(), (path.name, link)

sys.path.insert(0, str(root/"reference-model"))
spec = importlib.util.spec_from_file_location("bin_monitor_model_tests", root/"reference-model/test_detector.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
output = io.StringIO()
result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
files = ["reference-model/detector.py", "reference-model/test_detector.py", "design-profile.json", "requirements.md", "requirements-update.md"]
record = {
    "executed_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
    "scope":"Offline specification model and static engineering package only",
    "python":sys.version.split()[0],
    "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
    "model_result":"PASS" if result.wasSuccessful() else "FAIL",
    "static_checks":["23 acceptance IDs covered", "User dimensions and budget reflected", "Cost/threshold arithmetic", "SVG XML and local links", "No physical acceptance marked PASS"],
    "physical_acceptance":"NOT RUN","line_acceptance":"NOT RUN; setup BLOCKED",
    "erc":profile["erc"],"drc":profile["drc"],"kicad_check_record":"kicad/review/validation.json","product_complete":False,
    "sha256":{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files},
    "test_output":output.getvalue(),
}
(root/"evidence/model-check.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
print(output.getvalue())
print("Static design checks passed; evidence/model-check.json written.")
print("Physical and LINE acceptance remain NOT RUN. ERC/DRC: PASS_STATIC only.")
raise SystemExit(0 if result.wasSuccessful() else 1)
