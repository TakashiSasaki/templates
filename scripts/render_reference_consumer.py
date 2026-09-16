#!/usr/bin/env python3
"""Render Site self-description from public consumer declarations; never manage state."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import yaml

START = "<!-- reference-consumer:start -->"
END = "<!-- reference-consumer:end -->"


def project(root: Path):
    def read(path):
        return json.loads((root / path).read_text())
    discovery = read("reference-consumer.json")
    relations = discovery["relationships"]
    # Composition's lock-v2 ownership inventory is a documented public contract.
    # Policy configuration is public; Policy lock/adoption internals stay opaque.
    composition = read(relations["product"]["state"])
    intent = read(relations["product"]["intent"])
    policy = yaml.safe_load((root / relations["maintenance"]["configuration"]).read_text())
    publication = read(relations["publication"]["selection"])
    evidence = read("contracts/implementation-evidence.json")
    proof_statuses = [proof["status"] for record in evidence["records"]
                      for field in ("positiveEvidence", "negativeEvidence")
                      for proof in record[field]]
    return {"schema_version":1,"kind":"reference-consumer-description",
            "repository":discovery["repository"],"authority":"site",
            "composition":{"source":composition["source"],"intent":intent,
                           "ownership":composition["files"],"state":relations["product"]["state"]},
            "policy":{"toolchain":policy["toolchain"],"contexts":policy["contexts"],
                      "outputs":policy["outputs"],"configuration":relations["maintenance"]["configuration"],
                      "state":relations["maintenance"]["state"]},
            "publication":publication,
            "evidence":{"ledger":"contracts/implementation-evidence.json",
                        "verified":proof_statuses.count("verified"),
                        "deferred":proof_statuses.count("deferred")},
            "validation": {"composition":relations["product"]["validation"],
                           "policy_workflow":relations["maintenance"]["validation_workflow"],
                           "site_acceptance_workflow":".github/workflows/reference-consumer.yml"}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(project(args.repository),indent=2,ensure_ascii=False)+'\n')
