"""Live benchmark runner for ShopBot against tests.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


def evaluate_case(tc: dict[str, Any], data: dict[str, Any]) -> tuple[bool, str]:
    reply = data.get("reply", "")
    reply_lower = reply.lower()
    tool_names = [t.get("name", "") for t in data.get("tool_calls", [])]
    tokens = data.get("tokens", {})
    reasons: list[str] = []

    if tc.get("expect_blocked"):
        if tokens.get("in", -1) != 0 or tokens.get("out", -1) != 0:
            reasons.append(f"expected 0 tokens, got {tokens}")
        if tool_names:
            reasons.append(f"expected 0 tools, got {tool_names}")

    expected_tools = tc.get("expected_tools_any") or []
    if expected_tools and not any(t in tool_names for t in expected_tools):
        reasons.append(f"missing tool from {expected_tools} (got {tool_names})")

    must_any = tc.get("must_contain_any") or []
    if must_any and not any(needle.lower() in reply_lower for needle in must_any):
        reasons.append(f"reply missing any of {must_any}")

    must_not = tc.get("must_not_contain") or []
    for bad in must_not:
        if bad.lower() in reply_lower:
            reasons.append(f"reply contained forbidden '{bad}'")

    return (len(reasons) == 0), "; ".join(reasons)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ShopBot benchmark cases against deployed API")
    parser.add_argument("--url", default="http://localhost:8000", help="Agent API base URL")
    parser.add_argument("--tests", default=str(Path(__file__).resolve().parent.parent / "tests.json"))
    args = parser.parse_args()

    base = args.url.rstrip("/")
    cases = json.loads(Path(args.tests).read_text(encoding="utf-8"))
    run_id = uuid4().hex[:5]

    passed = 0
    total_in = 0
    total_out = 0
    failures: list[str] = []

    with httpx.Client(timeout=60.0) as client:
        health = client.get(f"{base}/health")
        print(f"GET /health -> {health.status_code} {health.text.strip()} (run_id={run_id})")

        print("\n| ID | Category | Status | Tools Called | Tokens (in/out) | Reply Preview |")
        print("| :--- | :--- | :---: | :--- | :---: | :--- |")

        for tc in cases:
            uid = tc["user_id"]
            tid = f"{run_id}-{tc['thread_id']}"
            setup_tid = f"{run_id}-{tc.get('setup_thread_id', tc['thread_id'])}"

            try:
                for msg in tc.get("setup_messages", []):
                    client.post(f"{base}/chat", json={"user_id": uid, "thread_id": setup_tid, "message": msg})

                resp = client.post(
                    f"{base}/chat",
                    json={"user_id": uid, "thread_id": tid, "message": tc["message"]},
                )
                data = resp.json()
                ok, reason = evaluate_case(tc, data)
            except Exception as exc:
                data = {"reply": f"ERROR: {exc}", "tool_calls": [], "tokens": {"in": 0, "out": 0}}
                ok, reason = False, str(exc)

            if ok:
                passed += 1
            else:
                failures.append(f"- {tc['id']}: {reason}")

            tok = data.get("tokens", {})
            t_in = int(tok.get("in", 0) or 0)
            t_out = int(tok.get("out", 0) or 0)
            total_in += t_in
            total_out += t_out
            tools = ", ".join(t["name"] for t in data.get("tool_calls", [])) or "none"
            preview = (data.get("reply", "").replace("\n", " ").replace("|", "/"))[:80]
            status_label = "PASS" if ok else "FAIL"
            print(f"| `{tc['id']}` | {tc['category']} | {status_label} | {tools} | {t_in}/{t_out} | {preview} |")

    pct = round((passed / len(cases)) * 100, 1) if cases else 0.0
    print(f"\n**Pass Rate:** {passed}/{len(cases)} ({pct}%) | **Total Tokens:** {total_in} in / {total_out} out")
    if failures:
        print("\n**Failures:**")
        for line in failures:
            print(line)


if __name__ == "__main__":
    main()
