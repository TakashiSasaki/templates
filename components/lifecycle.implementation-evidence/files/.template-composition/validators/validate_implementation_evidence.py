#!/usr/bin/env python3
"""Validate generic implementation-evidence semantics after schema validation."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from contract_common import contract_entries, load_json, load_manifest

def _duplicates(values):
    seen=set(); out=set()
    for value in values:
        if value in seen: out.add(value)
        seen.add(value)
    return out

def validate(root: Path) -> list[str]:
    errors=[]
    try:
        manifest=load_manifest(root); evidence=load_json(root/"contracts/implementation-evidence.json")
    except Exception as exc: return [f"cannot load implementation evidence: {exc}"]
    if not isinstance(evidence,dict): return ["implementation evidence must be an object"]
    commands=evidence.get("commands",[]); gates=evidence.get("releaseGates",[]); records=evidence.get("records",[]); mode=evidence.get("mode")
    command_ids=[x.get("id") for x in commands]; gate_ids=[x.get("id") for x in gates]; record_ids=[x.get("id") for x in records]
    for label,values in (("command",command_ids),("release gate",gate_ids),("record",record_ids)):
        for duplicate in sorted(_duplicates(values)): errors.append(f"duplicate implementation-evidence {label} id: {duplicate}")
    known_commands=set(command_ids); known_gates=set(gate_ids); known_contracts=contract_entries(manifest); used_commands=set(); used_gates=set(); proof_ids=[]
    gate_commands={}
    for gate in gates:
        refs=set(gate.get("commandIds",[])); gate_commands[gate["id"]]=refs
        for missing in sorted(refs-known_commands): errors.append(f"release gate {gate['id']}: unknown command {missing}")
    if mode=="template":
        if commands or gates or records: errors.append("template implementation evidence must be empty")
        return errors
    if mode!="product": return [f"unsupported implementation-evidence mode: {mode!r}"]
    for record in records:
        owner=f"record {record['id']}"; target=record.get("target",{}); cid=target.get("contractId")
        if cid not in known_contracts: errors.append(f"{owner}: unknown contract target {cid}")
        elif target.get("kind")=="contract-transition":
            transitions={(x["version"]-1,x["version"]) for x in known_contracts[cid]["versionHistory"][1:]}
            pair=(target.get("fromVersion"),target.get("toVersion"))
            if pair not in transitions: errors.append(f"{owner}: unknown contract transition {cid} {pair}")
        gate_refs=set(record.get("releaseGateIds",[])); used_gates.update(gate_refs)
        for missing in sorted(gate_refs-known_gates): errors.append(f"{owner}: unknown release gate {missing}")
        record_commands=set(); proofs=list(record.get("positiveEvidence",[]))+list(record.get("negativeEvidence",[])); proof_ids.extend(p.get("id") for p in proofs)
        for proof in proofs:
            command_id=proof.get("commandId")
            if command_id:
                used_commands.add(command_id); record_commands.add(command_id)
                if command_id not in known_commands: errors.append(f"{owner} proof {proof.get('id')}: unknown command {command_id}")
        gated=set()
        for gate_id in gate_refs: gated.update(gate_commands.get(gate_id,set()))
        for command_id in sorted(record_commands-gated): errors.append(f"{owner}: proof command {command_id} is not executed by a selected release gate")
    for duplicate in sorted(_duplicates(proof_ids)): errors.append(f"duplicate implementation-evidence proof id: {duplicate}")
    for unused in sorted(known_gates-used_gates): errors.append(f"unused implementation-evidence release gate: {unused}")
    for refs in gate_commands.values(): used_commands.update(refs)
    for unused in sorted(known_commands-used_commands): errors.append(f"unused implementation-evidence command: {unused}")
    return errors

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("root",nargs="?",default="."); args=parser.parse_args(); errors=validate(Path(args.root).resolve())
    if errors:
        for error in errors: print(f"ERROR: {error}",file=sys.stderr)
        return 1
    print("Implementation evidence validation: OK"); return 0
if __name__=="__main__": raise SystemExit(main())
