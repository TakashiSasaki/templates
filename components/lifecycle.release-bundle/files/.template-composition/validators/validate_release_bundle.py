#!/usr/bin/env python3
"""Validate deterministic release-bundle handoff metadata."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from contract_common import load_json, load_manifest, parse_timestamp, sha256_file
BUNDLE_ID="release_bundle"

def validate(root: Path, expected_revision: str|None)->list[str]:
    errors=[]
    try:
        manifest=load_manifest(root); release=load_json(root/"contracts/release-evidence.json"); bundle=load_json(root/"contracts/release-bundle.json")
    except Exception as exc: return [f"cannot load release-bundle inputs: {exc}"]
    mode=bundle.get("mode"); artifacts=bundle.get("artifacts",[])
    if mode=="template":
        if artifacts: errors.append("template release bundle must not contain artifacts")
        for field in ("subject","provenance","handoff"):
            if field in bundle: errors.append(f"template release bundle must not contain {field}")
        return errors
    if mode!="product": return [f"unsupported release-bundle mode: {mode!r}"]
    if expected_revision is None: return ["product release bundle requires --expected-revision"]
    if bundle.get("subject",{}).get("revision")!=expected_revision: errors.append("bundle subject does not match expected revision")
    if release.get("mode")!="product": errors.append("product release bundle requires product release evidence")
    if release.get("subject",{}).get("revision")!=expected_revision: errors.append("release-evidence subject does not match bundle revision")
    if release.get("decision",{}).get("status")!="approved": errors.append("release bundle requires approved release evidence")
    if bundle.get("handoff",{}).get("status")!="ready": errors.append("release bundle handoff must be ready")
    expected=[e for e in manifest.get("contracts",[]) if e.get("id")!=BUNDLE_ID]; expected_ids=[e["id"] for e in expected]; actual_ids=[a.get("contractId") for a in artifacts]
    if actual_ids!=expected_ids: errors.append(f"bundle artifacts must match manifest order excluding {BUNDLE_ID}: expected {expected_ids}, got {actual_ids}")
    by_id={e["id"]:e for e in expected}; seen=set()
    for artifact in artifacts:
        cid=artifact.get("contractId")
        if cid in seen: errors.append(f"duplicate bundle artifact: {cid}"); continue
        seen.add(cid); entry=by_id.get(cid)
        if entry is None: errors.append(f"unknown bundle artifact: {cid}"); continue
        if artifact.get("path")!=entry["document"]: errors.append(f"bundle artifact {cid}: path does not match manifest"); continue
        path=root/entry["document"]
        if not path.is_file(): errors.append(f"bundle artifact {cid}: document is missing"); continue
        if artifact.get("sha256")!=sha256_file(path): errors.append(f"bundle artifact {cid}: sha256 does not match current bytes")
    try:
        release_generated=parse_timestamp(release["provenance"]["generatedAt"]); bundle_generated=parse_timestamp(bundle["provenance"]["generatedAt"])
        if bundle_generated<release_generated: errors.append("release bundle generation precedes release evidence generation")
    except (KeyError,ValueError,TypeError) as exc: errors.append(f"invalid release-bundle chronology: {exc}")
    return errors

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("root",nargs="?",default="."); p.add_argument("--expected-revision"); a=p.parse_args(); errors=validate(Path(a.root).resolve(),a.expected_revision)
    if errors:
        for error in errors: print(f"ERROR: {error}",file=sys.stderr)
        return 1
    print("Release bundle validation: OK"); return 0
if __name__=="__main__": raise SystemExit(main())
