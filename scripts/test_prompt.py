"""Standalone tests for prompts/payment_prompt.py — no LiveKit, no network calls.

Usage: python scripts/test_prompt.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mock_data import get_config
from prompts.payment_prompt import build_payment_prompt
from state_machine import ALLOWED_ACTIONS, CallState, CallStateMachine

_failures = 0


def check(name: str, passed: bool) -> None:
    global _failures
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        _failures += 1


cfg = get_config()

# Build state + allowed_actions for an OPENING_DISCLOSURE context
sm = CallStateMachine()
sm.transition(CallState.OPENING_DISCLOSURE)
_state = sm.current_state.value
_actions = sm.allowed_actions

# ── Test 1: Prompt with identity_verified=False ───────────────────────────────
print("\n=== Test 1: build_payment_prompt(identity_verified=False, state=OPENING_DISCLOSURE) ===")
prompt_unverified = build_payment_prompt(cfg, identity_verified=False, current_state=_state, allowed_actions=_actions)
print(f"  [prompt length: {len(prompt_unverified)} chars]")
print(f"  [first 120 chars: {prompt_unverified[:120]!r}]")

check("agentName appears in prompt", cfg["agentName"] in prompt_unverified)
check("companyName appears in prompt", cfg["companyName"] in prompt_unverified)
check(
    "amountDueFormatted NOT in prompt",
    cfg["amountDueFormatted"] not in prompt_unverified,
)
check(
    "'Do not reveal any account details' appears",
    "Do not reveal any account details" in prompt_unverified,
)
check("CURRENT STATE block appears", "CURRENT STATE: OPENING_DISCLOSURE" in prompt_unverified)
check("allowed actions block appears", "IN THIS STATE YOU MAY ONLY:" in prompt_unverified)

# ── Test 2: Prompt with identity_verified=True ───────────────────────────────
print("\n=== Test 2: build_payment_prompt(identity_verified=True, state=PAYMENT_CONTEXT) ===")
_actions_pc = ALLOWED_ACTIONS[CallState.PAYMENT_CONTEXT]
prompt_verified = build_payment_prompt(
    cfg,
    identity_verified=True,
    current_state=CallState.PAYMENT_CONTEXT.value,
    allowed_actions=_actions_pc,
)
print(f"  [prompt length: {len(prompt_verified)} chars]")
print(f"  [first 120 chars: {prompt_verified[:120]!r}]")

check("amountDueFormatted appears in prompt", cfg["amountDueFormatted"] in prompt_verified)
check("dueDate appears in prompt", cfg["dueDate"] in prompt_verified)
check("customerName appears in prompt", cfg["customerName"] in prompt_verified)
check("CURRENT STATE block shows PAYMENT_CONTEXT", "CURRENT STATE: PAYMENT_CONTEXT" in prompt_verified)

# ── Test 3: 'legal action' absent from both prompts ──────────────────────────
print("\n=== Test 3: 'legal action' absent from both prompts ===")
check("'legal action' not in unverified prompt", "legal action" not in prompt_unverified)
check("'legal action' not in verified prompt", "legal action" not in prompt_verified)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
if _failures == 0:
    print("All tests PASSED")
else:
    print(f"{_failures} test(s) FAILED")
sys.exit(1 if _failures else 0)
