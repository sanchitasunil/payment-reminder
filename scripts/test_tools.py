"""Standalone tests for tools/payment_tools.py — no LiveKit, no network calls.

Usage: python scripts/test_tools.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from outcome_log import OutcomeLog
from tools.payment_tools import (
    create_dispute_ticket,
    end_call_wrong_person,
    flag_hardship,
    log_promise_to_pay,
    send_payment_link,
    verify_borrower_identity,
)

_failures = 0


def check(name: str, passed: bool) -> None:
    global _failures
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        _failures += 1


def _mock_job(outcome_log: OutcomeLog) -> MagicMock:
    job = MagicMock()
    job.proc.userdata = {"outcome_log": outcome_log}
    return job


def run(coro):
    return asyncio.run(coro)


# ── Test 1: verify_borrower_identity — correct digits ─────────────────────────
print("\n=== Test 1: verify_borrower_identity('1234') — correct ===")
log1 = OutcomeLog(scenario="test")
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log1)):
    r1 = run(verify_borrower_identity(digits="1234", context=MagicMock()))
print(f"  return: {r1!r}")
check("identity_verified set to True", log1.identity_verified is True)
check("returns non-empty string", bool(r1))

# ── Test 2: verify_borrower_identity — wrong digits ──────────────────────────
print("\n=== Test 2: verify_borrower_identity('9999') — wrong ===")
log2 = OutcomeLog(scenario="test")
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log2)):
    r2 = run(verify_borrower_identity(digits="9999", context=MagicMock()))
print(f"  return: {r2!r}")
check("identity_verified remains False", log2.identity_verified is False)
check("returns non-empty string", bool(r2))

# ── Test 3: send_payment_link before identity verified ───────────────────────
print("\n=== Test 3: send_payment_link before identity verified ===")
log3 = OutcomeLog(scenario="test")
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log3)):
    r3 = run(send_payment_link(context=MagicMock()))
print(f"  return: {r3!r}")
check("returns guard error string", "verified" in r3.lower() or "identity" in r3.lower())
check("payment_link_sent remains False", log3.payment_link_sent is False)

# ── Test 4: verify then send_payment_link ────────────────────────────────────
print("\n=== Test 4: verify('1234') then send_payment_link ===")
log4 = OutcomeLog(scenario="test")
job4 = _mock_job(log4)
with patch("tools.payment_tools.get_job_context", return_value=job4):
    run(verify_borrower_identity(digits="1234", context=MagicMock()))
    r4 = run(send_payment_link(context=MagicMock()))
print(f"  return: {r4!r}")
check("payment_link_sent is True", log4.payment_link_sent is True)
check("returns non-empty string", bool(r4))

# ── Test 5: log_promise_to_pay ───────────────────────────────────────────────
print("\n=== Test 5: log_promise_to_pay('June 25, 2026') ===")
log5 = OutcomeLog(scenario="test")
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log5)):
    r5 = run(log_promise_to_pay(promise_date="June 25, 2026", context=MagicMock()))
print(f"  return: {r5!r}")
check("promise_to_pay_date set", log5.promise_to_pay_date == "June 25, 2026")
check("outcome is 'promise_to_pay'", log5.outcome == "promise_to_pay")

# ── Test 6: create_dispute_ticket ────────────────────────────────────────────
print("\n=== Test 6: create_dispute_ticket ===")
log6 = OutcomeLog(scenario="test")
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log6)):
    r6 = run(create_dispute_ticket(context=MagicMock()))
print(f"  return: {r6!r}  ticket_id={log6.ticket_id!r}")
check("dispute_detected is True", log6.dispute_detected is True)
check("ticket_created is True", log6.ticket_created is True)
check("ticket_id starts with 'TKT-'", bool(log6.ticket_id) and log6.ticket_id.startswith("TKT-"))
check("future_automated_reminders_paused is True", log6.future_automated_reminders_paused is True)
check("outcome is 'payment_dispute'", log6.outcome == "payment_dispute")

# ── Test 7: flag_hardship ────────────────────────────────────────────────────
print("\n=== Test 7: flag_hardship('lost job') ===")
log7 = OutcomeLog(scenario="test")
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log7)):
    r7 = run(flag_hardship(reason="lost job", context=MagicMock()))
print(f"  return: {r7!r}")
check("hardship_detected is True", log7.hardship_detected is True)
check("human_callback_requested is True", log7.human_callback_requested is True)
check("outcome is 'hardship_detected'", log7.outcome == "hardship_detected")

# ── Test 8: end_call_wrong_person ────────────────────────────────────────────
print("\n=== Test 8: end_call_wrong_person ===")
log8 = OutcomeLog(scenario="test")
log8.amount_disclosed = True  # set up some state to verify it gets cleared
with patch("tools.payment_tools.get_job_context", return_value=_mock_job(log8)):
    r8 = run(end_call_wrong_person(context=MagicMock()))
print(f"  return: {r8!r}")
check("outcome is 'identity_mismatch'", log8.outcome == "identity_mismatch")
check("amount_disclosed is False", log8.amount_disclosed is False)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
if _failures == 0:
    print("All tests PASSED")
else:
    print(f"{_failures} test(s) FAILED")
sys.exit(1 if _failures else 0)
