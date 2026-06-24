"""Standalone test for the payment-reminder foundation layer.

Usage: python scripts/test_foundation.py
No LiveKit, no network, no .env required.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REQUIRED_CONFIG_KEYS = [
    "companyName", "agentName", "agentVoice", "useCase", "language",
    "customerName", "accountEnding", "registeredMobileLastFour",
    "amountDue", "amountDueFormatted", "dueDate", "daysPastDue",
    "scenario", "requireIdentityVerification", "recordingDisclosureRequired",
    "paymentLinkEnabled", "humanHandoffEnabled",
]

_failures = 0


def check(name: str, passed: bool) -> None:
    global _failures
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        _failures += 1


# ── Test 1: Load scenario_config.json ─────────────────────────────────────────
print("\n=== Test 1: Load scenario_config.json ===")
try:
    from mock_data import get_config
    cfg = get_config()
    for k, v in cfg.items():
        print(f"    {k}: {v!r}")
    check("scenario_config.json loaded", True)
    check("required keys present", all(k in cfg for k in REQUIRED_CONFIG_KEYS))
except Exception as exc:
    check("scenario_config.json loaded", False)
    check("required keys present", False)
    print(f"    ERROR: {exc}")

# ── Test 2: get_loan_account() ────────────────────────────────────────────────
print("\n=== Test 2: get_loan_account() ===")
try:
    from mock_data import get_loan_account
    acct = get_loan_account()
    print(f"    {acct}")
    check("customerName present", "customerName" in acct)
    check("amountDue present", "amountDue" in acct)
except Exception as exc:
    check("customerName present", False)
    check("amountDue present", False)
    print(f"    ERROR: {exc}")

# ── Test 3: has_grievance_pending() ──────────────────────────────────────────
print("\n=== Test 3: has_grievance_pending() ===")
try:
    from mock_data import get_scenario, has_grievance_pending
    result = has_grievance_pending()
    scenario = get_scenario()
    print(f"    has_grievance_pending() = {result}  (scenario={scenario!r})")
    check("result matches scenario", result == (scenario == "grievance_pending"))
except Exception as exc:
    check("result matches scenario", False)
    print(f"    ERROR: {exc}")

# ── Test 4–6: is_identity_match() ────────────────────────────────────────────
print("\n=== Tests 4–6: is_identity_match() ===")
try:
    from mock_data import is_identity_match
    r1 = is_identity_match("1234")
    r2 = is_identity_match("9999")
    r3 = is_identity_match("1 2 3 4")
    print(f"    is_identity_match('1234')   = {r1}")
    print(f"    is_identity_match('9999')   = {r2}")
    print(f"    is_identity_match('1 2 3 4') = {r3}")
    check("is_identity_match('1234') is True", r1 is True)
    check("is_identity_match('9999') is False", r2 is False)
    check("is_identity_match('1 2 3 4') is True", r3 is True)
except Exception as exc:
    check("is_identity_match('1234') is True", False)
    check("is_identity_match('9999') is False", False)
    check("is_identity_match('1 2 3 4') is True", False)
    print(f"    ERROR: {exc}")

# ── Test 7: OutcomeLog dataclass ──────────────────────────────────────────────
print("\n=== Test 7: OutcomeLog dataclass ===")
EXPECTED_FIELDS = [
    "scenario", "call_started", "recording_disclosure_played",
    "identity_verified", "amount_disclosed", "payment_link_sent",
    "promise_to_pay_date", "dispute_detected", "payment_reminder_stopped",
    "ticket_created", "ticket_id", "future_automated_reminders_paused",
    "hardship_detected", "human_callback_requested", "human_handoff_required",
    "outcome",
]
try:
    from outcome_log import OutcomeLog
    log = OutcomeLog(scenario="normal_reminder")
    log.call_started = True
    log.identity_verified = True
    log.outcome = "promise_to_pay"
    d = log.to_dict()
    print(f"    {d}")
    check("to_dict has all fields", all(f in d for f in EXPECTED_FIELDS))
except Exception as exc:
    check("to_dict has all fields", False)
    print(f"    ERROR: {exc}")

# ── Test 8: save_to_file() ────────────────────────────────────────────────────
print("\n=== Test 8: save_to_file() ===")
try:
    from outcome_log import OutcomeLog

    # Run from project root so logs/ lands in the right place
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    log = OutcomeLog(scenario="test_run")
    log.call_started = True
    path = log.save_to_file()
    print(f"    Written to: {path}")
    file_exists = os.path.isfile(path)
    check("file created in logs/", file_exists)
    if file_exists:
        with open(path, encoding="utf-8") as fh:
            contents = fh.read()
        parsed = json.loads(contents)
        check("saved file is valid JSON with fields", isinstance(parsed, dict) and "scenario" in parsed)
    else:
        check("saved file is valid JSON with fields", False)
except Exception as exc:
    check("file created in logs/", False)
    check("saved file is valid JSON with fields", False)
    print(f"    ERROR: {exc}")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
if _failures == 0:
    print("All tests PASSED")
else:
    print(f"{_failures} test(s) FAILED")
sys.exit(1 if _failures else 0)
