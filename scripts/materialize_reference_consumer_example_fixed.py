#!/usr/bin/env python3
"""Temporary wrapper correcting the ephemeral PWA route-policy field."""
from __future__ import annotations

import materialize_reference_consumer_example as materializer

_original_prepare = materializer.prepare_planning_state


def prepare_planning_state():
    product = _original_prepare()
    offline = materializer.load("contracts/pwa-offline.json")
    for item in offline["routePolicies"]:
        if item.get("routeId") == "site-reference-consumer" and "offlinePolicy" in item:
            item["offlineReadBehavior"] = item.pop("offlinePolicy")
    materializer.write("contracts/pwa-offline.json", offline)
    return product


materializer.prepare_planning_state = prepare_planning_state
materializer.main()
