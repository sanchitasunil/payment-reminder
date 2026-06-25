"""Standalone tests for guardrails.py — no LiveKit, no network, no .env required.

Usage: python scripts/test_guardrails.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from guardrails import GuardrailEngine

g = GuardrailEngine()
_failures = 0


def check(name: str, passed: bool) -> None:
    global _failures
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        _failures += 1


# ── check_pre_call ─────────────────────────────────────────────────────────────
print("\n=== check_pre_call: normal scenarios ===")

ok1, _ = g.check_pre_call("normal_reminder")
print(f"  normal_reminder → {ok1}")
check("normal_reminder can proceed", ok1 is True)

ok2, reason2 = g.check_pre_call("grievance_pending")
print(f"  grievance_pending → {ok2!r}  reason={reason2!r}")
check("grievance_pending is blocked", ok2 is False)
check("grievance block reason is non-empty", bool(reason2))

ok3, _ = g.check_pre_call("already_paid")
print(f"  already_paid → {ok3}")
check("already_paid can proceed", ok3 is True)


# ── should_stop_payment_flow ──────────────────────────────────────────────────
print("\n=== should_stop_payment_flow: dispute ===")

stop, reason = g.should_stop_payment_flow("I already paid this last week.")
print(f"  'I already paid this last week.' → {stop!r} / {reason!r}")
check("'already paid' triggers stop", stop is True)
check("reason is 'dispute'", reason == "dispute")

stop2, reason2 = g.should_stop_payment_flow("I am going to dispute this charge.")
print(f"  'I am going to dispute this charge.' → {stop2!r} / {reason2!r}")
check("'dispute' triggers stop", stop2 is True)
check("reason is 'dispute'", reason2 == "dispute")

print("\n=== should_stop_payment_flow: hardship ===")

stop3, reason3 = g.should_stop_payment_flow("I lost my job last month.")
print(f"  'I lost my job last month.' → {stop3!r} / {reason3!r}")
check("'lost my job' triggers stop", stop3 is True)
check("reason is 'hardship'", reason3 == "hardship")

stop4, reason4 = g.should_stop_payment_flow("I cannot pay, I'm in the hospital.")
print(f"  'I cannot pay, I'm in the hospital.' → {stop4!r} / {reason4!r}")
check("'cannot pay' triggers stop", stop4 is True)
check("reason is 'hardship'", reason4 == "hardship")

print("\n=== should_stop_payment_flow: human_requested / stop_calling ===")

stop5, reason5 = g.should_stop_payment_flow("I want to talk to a real person.")
print(f"  'I want to talk to a real person.' → {stop5!r} / {reason5!r}")
check("'real person' triggers stop", stop5 is True)
check("reason is 'human_requested'", reason5 == "human_requested")

stop6, reason6 = g.should_stop_payment_flow("Please stop calling me.")
print(f"  'Please stop calling me.' → {stop6!r} / {reason6!r}")
check("'stop calling me' triggers stop", stop6 is True)
check("reason is 'stop_calling'", reason6 == "stop_calling")

print("\n=== should_stop_payment_flow: no trigger ===")

stop7, reason7 = g.should_stop_payment_flow("Great, I will pay tomorrow.")
print(f"  'Great, I will pay tomorrow.' → {stop7!r} / {reason7!r}")
check("normal utterance does not trigger stop", stop7 is False)

stop8, reason8 = g.should_stop_payment_flow("Let me check my account.")
print(f"  'Let me check my account.' → {stop8!r} / {reason8!r}")
check("benign utterance does not trigger stop", stop8 is False)


# ── is_prohibited_language ────────────────────────────────────────────────────
print("\n=== is_prohibited_language ===")

proh1, phrase1 = g.is_prohibited_language("We will take legal action against you.")
print(f"  'legal action' → {proh1!r} / {phrase1!r}")
check("'legal action' is prohibited", proh1 is True)
check("matched phrase returned", "legal action" in phrase1)

proh2, phrase2 = g.is_prohibited_language("We will contact your family about this matter.")
print(f"  'contact your family' → {proh2!r} / {phrase2!r}")
check("'contact your family' is prohibited", proh2 is True)

proh3, _ = g.is_prohibited_language("Please pay your outstanding dues.")
print(f"  'pay your outstanding dues' → {proh3!r}")
check("benign agent text is not prohibited", proh3 is False)

proh4, _ = g.is_prohibited_language("I will escalate this to our team.")
print(f"  'escalate to our team' → {proh4!r}")
check("'escalate' alone is not prohibited", proh4 is False)


# ── check_wrong_person ────────────────────────────────────────────────────────
print("\n=== check_wrong_person (expected_name='Ramesh') ===")

wp1 = g.check_wrong_person("Wrong number, there's no Ramesh here.", "Ramesh")
print(f"  'Wrong number, no Ramesh here' → {wp1!r}")
check("'wrong number' detected as wrong person", wp1 is True)

wp2 = g.check_wrong_person("I am not Ramesh.", "Ramesh")
print(f"  'I am not Ramesh' → {wp2!r}")
check("'not Ramesh' detected as wrong person", wp2 is True)

wp3 = g.check_wrong_person("Yes, this is Ramesh speaking.", "Ramesh")
print(f"  'Yes, this is Ramesh speaking.' → {wp3!r}")
check("'Yes this is Ramesh' is NOT wrong person", wp3 is False)

wp4 = g.check_wrong_person("You have the wrong person.", "Ramesh")
print(f"  'You have the wrong person.' → {wp4!r}")
check("'wrong person' phrase detected", wp4 is True)


# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
if _failures == 0:
    print("All tests PASSED")
else:
    print(f"{_failures} test(s) FAILED")
sys.exit(1 if _failures else 0)
