"""PCOS CLI — command-line interface for the Context Broker.

Usage:
    pcos-route "Summarize this article" --task-type transform
    pcos-route "What language is this?" --webpage-grounded
    pcos-route "Write a research report" --exceeds-local-limits
"""
from __future__ import annotations

import argparse
import json
import sys

from broker.router.router import route
from broker.planner.planner import build_plan
from broker.context.context_schema import PCOSContext, TaskObject, TaskType, Sensitivity


def route_cli():
    parser = argparse.ArgumentParser(
        prog="pcos-route",
        description="PCOS Context Broker — route a task and print the decision",
    )
    parser.add_argument("text", help="Task text to route")
    parser.add_argument("--task-type", default="transform",
                        choices=["transform", "action", "reasoning", "retrieval"],
                        help="Task type")
    parser.add_argument("--short", action="store_true", default=True,
                        help="Task is short (<500 tokens)")
    parser.add_argument("--long", action="store_true",
                        help="Task exceeds local limits")
    parser.add_argument("--webpage-grounded", action="store_true",
                        help="Task is grounded in webpage content")
    parser.add_argument("--private", action="store_true",
                        help="Task contains private/sensitive data")
    parser.add_argument("--requires-action", action="store_true",
                        help="Task requires function calling")
    parser.add_argument("--requires-personal-context", action="store_true",
                        help="Task needs personal context from memory")
    parser.add_argument("--escalate", action="store_true",
                        help="User explicitly requests cloud escalation")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()

    task = TaskObject(
        text=args.text,
        task_type=TaskType(args.task_type),
        is_short=not args.long,
        is_webpage_grounded=args.webpage_grounded,
        sensitivity=Sensitivity.PRIVATE if args.private else Sensitivity.NORMAL,
        requires_action=args.requires_action,
        requires_personal_context=args.requires_personal_context,
        exceeds_local_limits=args.long,
        user_explicit_escalate=args.escalate,
    )
    ctx = PCOSContext()
    decision = route(task, ctx)
    plan = build_plan(decision, task, ctx)

    if args.json:
        print(json.dumps({
            "decision": {
                "surface": decision.surface if isinstance(decision.surface, str) else decision.surface.value,
                "chrome_api": decision.chrome_api if isinstance(decision.chrome_api, str) else (decision.chrome_api.value if decision.chrome_api else None),
                "reason": decision.reason,
                "escalate_to_cloud": decision.escalate_to_cloud,
                "latency_target_ms": decision.latency_target_ms,
            },
            "plan": plan.model_dump(),
        }, indent=2))
    else:
        surface = decision.surface if isinstance(decision.surface, str) else decision.surface.value
        api = decision.chrome_api if isinstance(decision.chrome_api, str) else (decision.chrome_api.value if decision.chrome_api else "N/A")
        print(f"Surface:     {surface}")
        print(f"Chrome API:  {api}")
        print(f"Reason:      {decision.reason}")
        print(f"Cloud:       {'Yes' if decision.escalate_to_cloud else 'No'}")
        print(f"Latency:     {decision.latency_target_ms}ms target")
        print(f"Plan steps:  {len(decision.tool_plan)}")

    return 0


if __name__ == "__main__":
    sys.exit(route_cli())
