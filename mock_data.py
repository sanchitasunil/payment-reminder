from __future__ import annotations

import json
import os
import re

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_config.json")


def get_config() -> dict:
    """Read scenario_config.json fresh from disk on every call.

    This allows scripts/trigger_call.py to update the scenario between calls
    without restarting the agent worker process.
    """
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_loan_account() -> dict:
    cfg = get_config()
    return {
        "customerName": cfg["customerName"],
        "accountEnding": cfg["accountEnding"],
        "amountDue": cfg["amountDue"],
        "amountDueFormatted": cfg["amountDueFormatted"],
        "dueDate": cfg["dueDate"],
        "daysPastDue": cfg["daysPastDue"],
        "registeredMobileLastFour": cfg["registeredMobileLastFour"],
    }


def has_grievance_pending() -> bool:
    return get_config().get("scenario") == "grievance_pending"


def is_identity_match(digits_provided: str) -> bool:
    cleaned = re.sub(r"\D", "", digits_provided.strip())
    return cleaned == str(get_config()["registeredMobileLastFour"])


def get_scenario() -> str:
    return get_config()["scenario"]
