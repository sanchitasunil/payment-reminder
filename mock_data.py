from __future__ import annotations

import json
import os
import re

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_config.json")

with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _CONFIG: dict = json.load(_f)


def get_config() -> dict:
    return _CONFIG


def get_loan_account() -> dict:
    return {
        "customerName": _CONFIG["customerName"],
        "accountEnding": _CONFIG["accountEnding"],
        "amountDue": _CONFIG["amountDue"],
        "amountDueFormatted": _CONFIG["amountDueFormatted"],
        "dueDate": _CONFIG["dueDate"],
        "daysPastDue": _CONFIG["daysPastDue"],
        "registeredMobileLastFour": _CONFIG["registeredMobileLastFour"],
    }


def has_grievance_pending() -> bool:
    return _CONFIG.get("scenario") == "grievance_pending"


def is_identity_match(digits_provided: str) -> bool:
    cleaned = re.sub(r"\D", "", digits_provided.strip())
    return cleaned == str(_CONFIG["registeredMobileLastFour"])


def get_scenario() -> str:
    return _CONFIG["scenario"]
