from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"guard failed for {path}: expected one occurrence, got {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


def insert_before_validate(path: str, helper: str) -> None:
    marker = "\n\ndef validate(root: Path) -> list[str]:\n"
    replace_once(path, marker, "\n\n" + helper.rstrip() + marker)


# CLI
cli = "components/capability.cli/files/.template-composition/validators/validate_cli_interface.py"
insert_before_validate(cli, r'''
def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    errors: list[str] = []
    allowed = ", ".join(sorted(EXECUTABLE_PROOF_KINDS))
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "cli_interface":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] != "entrypoint":
                errors.append(
                    f"CLI planning requirement {requirement_id!r} has unsupported target {key}; "
                    "CLI planning targets must be contract-item/cli_interface/entrypoint"
                )
            elif declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"CLI planning requirement {requirement_id!r} targets entrypoint "
                    f"{key[3]!r} and must declare an executable requiredPositiveProofKinds "
                    f"value ({allowed})"
                )
    return errors
''')
replace_once(
    cli,
    '    cli_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if cli_mode == "template":\n',
    '    cli_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if evidence_mode == "planning":\n        return planning_requirement_errors(evidence)\n\n    if cli_mode == "template":\n',
)
replace_once(
    cli,
    '    contract = load_json(root, CLI_CONTRACT)\n    if contract.get("mode") == "template":\n        print("CLI interface: template mode OK; no product CLI claim is active")\n',
    '    contract = load_json(root, CLI_CONTRACT)\n    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)\n    if evidence.get("mode") == "planning":\n        print("CLI planning targets and executable proof strength: OK")\n    elif contract.get("mode") == "template":\n        print("CLI interface: template mode OK; no product CLI claim is active")\n',
)

# Service
service = "components/capability.service/files/.template-composition/validators/validate_service_interface.py"
insert_before_validate(service, r'''
def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    errors: list[str] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "service_interface":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] != "operation":
                errors.append(
                    f"service planning requirement {requirement_id!r} has unsupported target {key}; "
                    "service planning targets must be contract-item/service_interface/operation"
                )
            elif declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"service planning requirement {requirement_id!r} targets operation "
                    f"{key[3]!r} and must declare an executable requiredPositiveProofKinds "
                    f"value from {sorted(EXECUTABLE_PROOF_KINDS)}"
                )
    return errors
''')
replace_once(
    service,
    '    service_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n    if service_mode == "template":\n',
    '    service_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n    if evidence_mode == "planning":\n        return planning_requirement_errors(evidence)\n    if service_mode == "template":\n',
)
replace_once(
    service,
    '    print("Service interface coverage and executable evidence strength: OK")\n',
    '    evidence = load_json(Path(args.root).resolve(), IMPLEMENTATION_EVIDENCE)\n    if evidence.get("mode") == "planning":\n        print("Service planning targets and executable proof strength: OK")\n    else:\n        print("Service interface coverage and executable evidence strength: OK")\n',
)

# Web interface
web = "components/capability.web-interface/files/.template-composition/validators/validate_web_interface.py"
replace_once(
    web,
    'EXECUTABLE_PROOF_KINDS = frozenset({"integration-test", "end-to-end-test"})\n',
    'EXECUTABLE_PROOF_KINDS = frozenset({"integration-test", "end-to-end-test"})\nPLANNING_ENDPOINT_PROOF_KINDS = BROWSER_PROOF_KINDS | EXECUTABLE_PROOF_KINDS\n',
)
insert_before_validate(web, r'''
def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    errors: list[str] = []
    allowed = ", ".join(sorted(PLANNING_ENDPOINT_PROOF_KINDS))
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "web_interface":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] != "endpoint":
                errors.append(
                    f"Web interface planning requirement {requirement_id!r} has unsupported "
                    f"target {key}; planning targets must be contract-item/web_interface/endpoint"
                )
            elif declared.isdisjoint(PLANNING_ENDPOINT_PROOF_KINDS):
                errors.append(
                    f"Web interface planning requirement {requirement_id!r} targets endpoint "
                    f"{key[3]!r} and must declare a non-static requiredPositiveProofKinds "
                    f"value ({allowed}); exact browser/executable subtype strength is enforced "
                    "after the product endpoint kind is declared"
                )
    return errors
''')
replace_once(
    web,
    '    interface_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if interface_mode == "template":\n',
    '    interface_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if evidence_mode == "planning":\n        return planning_requirement_errors(evidence)\n\n    if interface_mode == "template":\n',
)
replace_once(
    web,
    '    contract = load_json(root, WEB_INTERFACE_CONTRACT)\n    if contract.get("mode") == "template":\n        print("Web interface: template mode OK; no product endpoint claim is active")\n',
    '    contract = load_json(root, WEB_INTERFACE_CONTRACT)\n    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)\n    if evidence.get("mode") == "planning":\n        print("Web interface planning targets and non-static proof strength: OK")\n    elif contract.get("mode") == "template":\n        print("Web interface: template mode OK; no product endpoint claim is active")\n',
)

# MCP
mcp = "components/capability.mcp/files/.template-composition/validators/validate_mcp_interface.py"
insert_before_validate(mcp, r'''
def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    errors: list[str] = []
    allowed = ", ".join(sorted(EXECUTABLE_PROOF_KINDS))
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "mcp_interface":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key[0] != "contract-item" or key[2] not in {"transport", "operation"}:
                errors.append(
                    f"MCP planning requirement {requirement_id!r} has unsupported target {key}; "
                    "MCP planning targets must be transport or operation contract items"
                )
            elif declared.isdisjoint(EXECUTABLE_PROOF_KINDS):
                errors.append(
                    f"MCP planning requirement {requirement_id!r} targets {key[2]} "
                    f"{key[3]!r} and must declare an executable requiredPositiveProofKinds "
                    f"value ({allowed})"
                )
    return errors
''')
replace_once(
    mcp,
    '    mcp_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if mcp_mode == "template":\n',
    '    mcp_mode = contract.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if evidence_mode == "planning":\n        return planning_requirement_errors(evidence)\n\n    if mcp_mode == "template":\n',
)
replace_once(
    mcp,
    '    contract = load_json(root, MCP_CONTRACT)\n    if contract.get("mode") == "template":\n        print("MCP interface: template mode OK; no product transport/operation claim is active")\n',
    '    contract = load_json(root, MCP_CONTRACT)\n    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)\n    if evidence.get("mode") == "planning":\n        print("MCP planning targets and executable proof strength: OK")\n    elif contract.get("mode") == "template":\n        print("MCP interface: template mode OK; no product transport/operation claim is active")\n',
)

# MCP Apps
apps = "components/capability.mcp-apps/files/.template-composition/validators/validate_mcp_apps.py"
insert_before_validate(apps, r'''
def planning_requirement_errors(evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        return ["planning implementation-evidence requirements must be an array"]
    policies = {
        "extension": EXTENSION_PROOF_KINDS,
        "view": VIEW_PROOF_KINDS,
        "association": ASSOCIATION_PROOF_KINDS,
    }
    errors: list[str] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        for target in requirement.get("targets", []):
            key = target_key(target)
            if key[1] != "mcp_apps":
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            item_kind = key[2]
            allowed = policies.get(item_kind)
            if key[0] != "contract-item" or allowed is None:
                errors.append(
                    f"MCP Apps planning requirement {requirement_id!r} has unsupported "
                    f"target {key}; Apps planning targets must be extension, view, or association items"
                )
                continue
            if item_kind == "extension" and key[3] != "mcp-apps":
                errors.append(
                    f"MCP Apps planning requirement {requirement_id!r} must use the stable "
                    "extension target id 'mcp-apps'"
                )
            if declared.isdisjoint(allowed):
                errors.append(
                    f"MCP Apps planning requirement {requirement_id!r} targets {item_kind} "
                    f"{key[3]!r} and must declare compatible requiredPositiveProofKinds "
                    f"({', '.join(sorted(allowed))})"
                )
    return errors
''')
replace_once(
    apps,
    '    apps_mode = apps.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if apps_mode == "template":\n',
    '    apps_mode = apps.get("mode")\n    evidence_mode = evidence.get("mode")\n\n    if evidence_mode == "planning":\n        return planning_requirement_errors(evidence)\n\n    if apps_mode == "template":\n',
)
replace_once(
    apps,
    '    print("MCP Apps contract/evidence coverage: OK")\n',
    '    evidence = load_json(root, IMPLEMENTATION_EVIDENCE)\n    if evidence.get("mode") == "planning":\n        print("MCP Apps planning targets and proof strength: OK")\n    else:\n        print("MCP Apps contract/evidence coverage: OK")\n',
)

# Webapp planning validation
webapp = "components/artifact.webapp-core/files/scripts/validate_webapp_evidence.py"
helper = r'''
def planning_requirement_errors(root: Path, evidence: dict[str, Any]) -> list[str]:
    requirements = evidence.get("requirements")
    if not isinstance(requirements, list):
        raise TypeError("implementation evidence requirements must be a JSON array")
    allowed = {target_key(target) for target in allowed_targets(root)}
    allowed_kinds = ", ".join(sorted(BROWSER_LEVEL_PROOF_KINDS))
    errors: list[str] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise TypeError(f"implementation evidence requirement {index} must be a JSON object")
        declared = {
            kind
            for kind in requirement.get("requiredPositiveProofKinds", [])
            if isinstance(kind, str)
        }
        targets = requirement.get("targets")
        if not isinstance(targets, list):
            raise TypeError(
                f"implementation evidence requirement {index} targets must be a JSON array"
            )
        for target in targets:
            if not isinstance(target, dict):
                raise TypeError(
                    f"implementation evidence requirement {index} target must be a JSON object"
                )
            key = target_key(target)
            if len(key) < 2 or key[1] not in DOMAIN_IDS:
                continue
            requirement_id = requirement.get("id", f"index-{index}")
            if key not in allowed:
                errors.append(
                    f"unknown planning Webapp requirement target for {requirement_id!r}: {key}"
                )
            if requires_browser_level_proof(target) and declared.isdisjoint(
                BROWSER_LEVEL_PROOF_KINDS
            ):
                errors.append(
                    f"planning requirement {requirement_id!r} targets browser-sensitive "
                    f"Webapp item {key} and must declare at least one browser-level "
                    f"requiredPositiveProofKinds value ({allowed_kinds})"
                )
    return errors
'''
marker = "\n\ndef main() -> int:\n"
replace_once(webapp, marker, "\n\n" + helper.rstrip() + marker)
replace_once(
    webapp,
    '        if mode == "planning":\n            print("Webapp evidence coverage: planning mode; product target coverage pending")\n            return 0\n',
    '        if mode == "planning":\n            planning_errors = planning_requirement_errors(root, evidence)\n            if planning_errors:\n                for error in planning_errors:\n                    print(f"ERROR: {error}", file=sys.stderr)\n                return 1\n            print("Webapp planning targets and browser proof strength: OK")\n            return 0\n',
)

# Preserve target-bound planning details in Webapp worklist projection.
scaffold = "components/artifact.webapp-core/files/scripts/scaffold_webapp_evidence.py"
replace_once(
    scaffold,
    '        item["requiredPositiveProofKinds"] = list(required_kinds)\n\n        if mode == "planning":\n',
    '        item["requiredPositiveProofKinds"] = list(required_kinds)\n        targets = requirement.get("targets")\n        if targets is not None:\n            if not isinstance(targets, list):\n                raise ValueError(\n                    f"canonical requirement {requirement_id!r} has invalid targets"\n                )\n            item["targets"] = list(targets)\n\n        if mode == "planning":\n',
)

# Component version bumps for changed managed materials.
for path, old, new in [
    ("components/artifact.webapp-core/component.json", 11, 12),
    ("components/capability.cli/component.json", 2, 3),
    ("components/capability.service/component.json", 2, 3),
    ("components/capability.web-interface/component.json", 2, 3),
    ("components/capability.mcp/component.json", 2, 3),
    ("components/capability.mcp-apps/component.json", 2, 3),
]:
    replace_once(path, f'"version": {old}', f'"version": {new}')
