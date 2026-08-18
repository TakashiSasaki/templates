#!/usr/bin/env python3
"""Validate Webapp-specific implementation-evidence target coverage."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOMAIN_IDS={"surfaces","routes","ui_states","viewports"}

def load(relative):
    return json.loads((ROOT/relative).read_text(encoding="utf-8"))

def expected_targets():
    manifest=load("contracts/manifest.json"); surfaces=load("contracts/surfaces.json"); routes=load("contracts/routes.json"); states=load("contracts/ui-states.json"); viewports=load("contracts/viewports.json")
    expected=set()
    expected.update(("contract-item","surfaces","surface",x["id"]) for x in surfaces["surfaces"])
    expected.update(("contract-item","routes","route",x["id"]) for x in routes["routes"])
    expected.update(("contract-item","ui_states","ui-state",x["id"]) for x in states["states"])
    expected.update(("contract-item","viewports","viewport",x["id"]) for x in viewports["viewports"])
    expected.update(("contract-item","viewports","input-capability",x) for x in viewports["inputCapabilities"])
    for entry in manifest["contracts"]:
        if entry["id"] not in DOMAIN_IDS: continue
        for transition in entry["versionHistory"][1:]:
            expected.add(("contract-transition",entry["id"],transition["version"]-1,transition["version"]))
    return expected

def key(target):
    if target.get("kind")=="contract-transition": return ("contract-transition",target.get("contractId"),target.get("fromVersion"),target.get("toVersion"))
    return ("contract-item",target.get("contractId"),target.get("itemKind"),target.get("itemId"))

def main()->int:
    evidence=load("contracts/implementation-evidence.json")
    if evidence.get("mode")=="template":
        print("Webapp evidence coverage: template mode OK"); return 0
    actual=[key(record["target"]) for record in evidence.get("records",[])]
    errors=[]
    if len(actual)!=len(set(actual)): errors.append("duplicate Webapp implementation-evidence target")
    expected=expected_targets(); actual_set=set(actual)
    for missing in sorted(expected-actual_set,key=str): errors.append(f"missing Webapp implementation-evidence target: {missing}")
    for extra in sorted(actual_set-expected,key=str): errors.append(f"unknown Webapp implementation-evidence target: {extra}")
    if errors:
        for error in errors: print(f"ERROR: {error}",file=sys.stderr)
        return 1
    print("Webapp evidence coverage: OK"); return 0
if __name__=="__main__": raise SystemExit(main())
