"""Standalone tests for state_machine.py — no LiveKit, no network, no .env required.

Usage: python scripts/test_state_machine.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from state_machine import ALLOWED_ACTIONS, CallState, CallStateMachine

_failures = 0


def check(name: str, passed: bool) -> None:
    global _failures
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        _failures += 1


# ── Test 1: Initial state ─────────────────────────────────────────────────────
print("\n=== Test 1: Initial state is PRE_CALL_CHECK ===")
sm1 = CallStateMachine()
print(f"  current_state = {sm1.current_state.value!r}")
check("initial state is PRE_CALL_CHECK", sm1.current_state == CallState.PRE_CALL_CHECK)

# ── Test 2: Valid transition ───────────────────────────────────────────────────
print("\n=== Test 2: PRE_CALL_CHECK → OPENING_DISCLOSURE returns True ===")
sm2 = CallStateMachine()
result = sm2.transition(CallState.OPENING_DISCLOSURE)
print(f"  transition returned: {result}")
print(f"  current_state: {sm2.current_state.value!r}")
check("transition returns True", result is True)
check("state advanced to OPENING_DISCLOSURE", sm2.current_state == CallState.OPENING_DISCLOSURE)

# ── Test 3: Invalid transition (state unchanged) ───────────────────────────────
print("\n=== Test 3: PRE_CALL_CHECK → PAYMENT_CONTEXT returns False, state unchanged ===")
sm3 = CallStateMachine()
result3 = sm3.transition(CallState.PAYMENT_CONTEXT)
print(f"  transition returned: {result3}")
print(f"  current_state: {sm3.current_state.value!r}")
check("invalid transition returns False", result3 is False)
check("state unchanged after invalid transition", sm3.current_state == CallState.PRE_CALL_CHECK)

# ── Test 4: Terminal state ─────────────────────────────────────────────────────
print("\n=== Test 4: Transition to HUMAN_HANDOFF → is_terminal() == True ===")
sm4 = CallStateMachine()
sm4.transition(CallState.OPENING_DISCLOSURE)
sm4.transition(CallState.HUMAN_HANDOFF)
print(f"  current_state: {sm4.current_state.value!r}")
print(f"  is_terminal: {sm4.is_terminal()}")
check("transitioned to HUMAN_HANDOFF", sm4.current_state == CallState.HUMAN_HANDOFF)
check("is_terminal() is True", sm4.is_terminal() is True)

# ── Test 5: Cannot transition out of terminal state ────────────────────────────
print("\n=== Test 5: Transition out of HUMAN_HANDOFF returns False ===")
sm5 = CallStateMachine()
sm5.transition(CallState.OPENING_DISCLOSURE)
sm5.transition(CallState.HUMAN_HANDOFF)
result5 = sm5.transition(CallState.CALL_SUMMARY)
print(f"  transition returned: {result5}")
print(f"  current_state: {sm5.current_state.value!r}")
check("transition out of terminal returns False", result5 is False)
check("state stays at HUMAN_HANDOFF", sm5.current_state == CallState.HUMAN_HANDOFF)

# ── Test 6: Full normal_reminder path ─────────────────────────────────────────
print("\n=== Test 6: Full normal_reminder path (8 states) ===")
normal_path = [
    CallState.PRE_CALL_CHECK,
    CallState.OPENING_DISCLOSURE,
    CallState.IDENTITY_VERIFICATION,
    CallState.PAYMENT_CONTEXT,
    CallState.INTENT_CLASSIFICATION,
    CallState.SEND_PAYMENT_LINK,
    CallState.PROMISE_TO_PAY,
    CallState.CALL_SUMMARY,
]
sm6 = CallStateMachine()
all_ok = True
for next_state in normal_path[1:]:
    ok = sm6.transition(next_state)
    if not ok:
        print(f"  FAILED transition to {next_state.value}")
        all_ok = False
hist = sm6.history()
print(f"  history: {hist}")
check("all 7 transitions succeed", all_ok)
check("history has 8 entries", len(hist) == 8)
check("history matches expected path", hist == [s.value for s in normal_path])

# ── Test 7: PAYMENT_CONTEXT allowed_actions contains 'state amount due' ────────
print("\n=== Test 7: PAYMENT_CONTEXT allowed_actions contains 'state amount due' ===")
actions_pc = ALLOWED_ACTIONS[CallState.PAYMENT_CONTEXT]
print(f"  allowed_actions: {actions_pc}")
check(
    "at least one action contains 'state amount due'",
    any("state amount due" in a for a in actions_pc),
)

# ── Test 8: PRE_CALL_CHECK allowed_actions is empty list ──────────────────────
print("\n=== Test 8: PRE_CALL_CHECK allowed_actions is empty list ===")
sm8 = CallStateMachine()
actions_pre = sm8.allowed_actions
print(f"  allowed_actions: {actions_pre!r}")
check("PRE_CALL_CHECK allowed_actions is []", actions_pre == [])

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
if _failures == 0:
    print("All tests PASSED")
else:
    print(f"{_failures} test(s) FAILED")
sys.exit(1 if _failures else 0)
