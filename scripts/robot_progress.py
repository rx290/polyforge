#!/usr/bin/env python3
"""Update the Madlab HQ dashboard card for the robotics work.

usage: robot_progress.py <step_index> <state> [note] [--percent N] [--status S] [--log "line"] [--output label=/abs/path]
       robot_progress.py --init
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

P = Path.home() / "madlab-hq/progress/robotics.json"
STEPS = [
    "Read existing polyforge robot builder",
    "Research: component library with datasheet dimensions + sources",
    "Library JSON schema + validation test",
    "Mount generators (trays, standoffs, clips, enclosures, servo brackets, motor mounts, batteries)",
    "STL validation script + contact sheet renders",
    "Wiring research doc (open robot designs)",
    "Wiring features: channels, hollow-axis joints, clips, drag chain",
    "Builder integration: spec names library parts",
    "Demo: quadruped (SpotMicro-like) + biped with BOM and assembly notes",
    "Tests, commit, push",
]


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", nargs="?", type=int)
    ap.add_argument("state", nargs="?")
    ap.add_argument("note", nargs="?", default=None)
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--percent", type=int)
    ap.add_argument("--status")
    ap.add_argument("--log")
    ap.add_argument("--eta", help="ISO time the work should finish")
    ap.add_argument("--output", action="append", default=[])
    a = ap.parse_args()
    if a.init or not P.exists():
        d = {"name": "Robotics", "updated": now(), "status": "running", "percent": 0,
             "steps": [{"title": t, "state": "todo", "note": ""} for t in STEPS], "outputs": [], "log": []}
    else:
        d = json.loads(P.read_text())
    if a.step is not None:
        s = d["steps"][a.step]
        s["state"] = a.state or s["state"]
        if a.note is not None:
            s["note"] = a.note
    if a.percent is not None:
        d["percent"] = a.percent
    if a.eta:
        d["eta"] = a.eta
    if a.status:
        d["status"] = a.status
    for o in a.output:
        label, path = o.split("=", 1)
        d["outputs"] = [x for x in d["outputs"] if x["label"] != label] + [{"label": label, "path": path}]
    if a.log:
        d["log"].append(f"{datetime.now().strftime('%H:%M')} {a.log}")
        d["log"] = d["log"][-40:]
    d["updated"] = now()
    P.parent.mkdir(parents=True, exist_ok=True)
    P.write_text(json.dumps(d, indent=1))


if __name__ == "__main__":
    main()
