#!/usr/bin/env python3
"""Validate revision-bound release evidence against implementation commands and gates."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from contract_common import load_json, parse_timestamp, sha256_text
from validate_implementation_evidence import requirement_traceability_errors

def _index(items,key):
    result={}; errors=[]
    for item in items:
        value=item.get(key)
        if value in result: errors.append(f"duplicate {key}: {value}")
        result[value]=item
    return result,errors

def validate(root: Path, expected_revision: str|None)->list[str]:
    errors=[]
    try:
        implementation=load_json(root/"contracts/implementation-evidence.json"); release=load_json(root/"contracts/release-evidence.json")
    except Exception as exc: return [f"cannot load release evidence inputs: {exc}"]
    mode=release.get("mode"); command_results=release.get("commandResults",[]); gate_results=release.get("gateResults",[])
    if mode=="template":
        if command_results or gate_results: errors.append("template release evidence must not contain results")
        for field in ("subject","provenance","decision"):
            if field in release: errors.append(f"template release evidence must not contain {field}")
        return errors
    if mode!="product": return [f"unsupported release-evidence mode: {mode!r}"]
    if expected_revision is None: return ["product release evidence requires --expected-revision"]
    if release.get("subject",{}).get("revision")!=expected_revision: errors.append("release subject does not match expected revision")
    commands,e=_index(implementation.get("commands",[]),"id"); errors.extend(e); gates,e=_index(implementation.get("releaseGates",[]),"id"); errors.extend(e)
    errors.extend(requirement_traceability_errors(implementation))
    result_commands,e=_index(command_results,"commandId"); errors.extend(e); result_gates,e=_index(gate_results,"gateId"); errors.extend(e)
    expected_commands=set()
    for gate in gates.values(): expected_commands.update(gate.get("commandIds",[]))
    if set(result_commands)!=expected_commands: errors.append(f"release command results must exactly cover gated commands: expected {sorted(expected_commands)}, got {sorted(result_commands)}")
    if set(result_gates)!=set(gates): errors.append(f"release gate results must exactly cover release gates: expected {sorted(gates)}, got {sorted(result_gates)}")
    completed=[]
    for cid,result in result_commands.items():
        command=commands.get(cid)
        if command is None: errors.append(f"unknown release command result: {cid}"); continue
        if result.get("commandDigest")!=sha256_text(command["command"]): errors.append(f"release command {cid}: commandDigest does not match authoritative command")
        if result.get("status")!="passed" or result.get("exitCode")!=0: errors.append(f"release command {cid}: release requires passed status and exitCode 0")
        try:
            started=parse_timestamp(result["startedAt"]); finished=parse_timestamp(result["completedAt"])
            if finished<started: errors.append(f"release command {cid}: completedAt precedes startedAt")
            completed.append(finished)
        except (KeyError,ValueError,TypeError) as exc: errors.append(f"release command {cid}: invalid chronology: {exc}")
    for gid,result in result_gates.items():
        if gid not in gates: errors.append(f"unknown release gate result: {gid}")
        if result.get("status")!="passed": errors.append(f"release gate {gid}: release requires passed status")
    decision=release.get("decision",{})
    if decision.get("status")!="approved": errors.append("release decision must be approved")
    try:
        decided=parse_timestamp(decision["decidedAt"]); generated=parse_timestamp(release["provenance"]["generatedAt"])
        if completed and decided<max(completed): errors.append("release approval precedes command completion")
        if generated<decided: errors.append("release evidence generation precedes release approval")
    except (KeyError,ValueError,TypeError) as exc: errors.append(f"invalid release evidence chronology: {exc}")
    return errors

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("root",nargs="?",default="."); p.add_argument("--expected-revision"); a=p.parse_args(); errors=validate(Path(a.root).resolve(),a.expected_revision)
    if errors:
        for error in errors: print(f"ERROR: {error}",file=sys.stderr)
        return 1
    print("Release evidence validation: OK"); return 0
if __name__=="__main__": raise SystemExit(main())
