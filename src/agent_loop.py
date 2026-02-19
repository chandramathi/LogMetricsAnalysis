"""
agent_loop.py  —  PART 2: The Agent Loop
"""

import json
import re
import os
from groq import Groq
from agent_tools import TOOLS, TOOL_FUNCTIONS, write_bug_report

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Fallback list — if a model is decommissioned we try the next one automatically
MODELS = [
    "llama-3.3-70b-versatile",                      # Groq recommended (2025)
    "meta-llama/llama-4-scout-17b-16e-instruct",    # Llama 4 fallback
    "llama-3.1-70b-versatile",                       # Older fallback
]

SYSTEM_PROMPT = """You are a Java bug analyst. Use the available tools to analyze log files, then write a report.

Follow these steps in order:
1. Call list_log_files to see what logs exist
2. Call summarize_log_stats on each log file
3. Call search_log_patterns for: ERROR, NullPointerException, GC_ALERT, DEADLOCK
4. After all tool calls are complete, write a full markdown bug report as your final plain-text response.

The final report must include: Executive Summary, Critical Bugs with Java code fixes, Performance Issues, Root Cause Analysis.
"""


# ── Argument parsing ────────────────────────────────────────────────────────

def safe_parse_args(raw: str) -> dict:
    """Parse tool call JSON with multiple fallback strategies."""
    if not raw or not raw.strip():
        return {}
    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Escape bare newlines/tabs that break JSON string values
    try:
        cleaned = re.sub(r'(?<!\\)\n', r'\\n', raw)
        cleaned = re.sub(r'(?<!\\)\r', r'\\r', cleaned)
        cleaned = re.sub(r'(?<!\\)\t', r'\\t', cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Regex key:value extraction as last resort
    try:
        result = {}
        for m in re.finditer(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL):
            result[m.group(1)] = m.group(2).replace('\\n', '\n')
        if result:
            print(f"    Regex fallback parsed keys: {list(result.keys())}")
            return result
    except Exception:
        pass
    print(f"   Could not parse tool args: {raw[:150]}")
    return {"_parse_error": True}


# ── Inline function call detection ──────────────────────────────────────────

def detect_inline_function_call(text: str):
    """
    Detect when the LLM outputs a tool call as plain text, e.g.:
      <function=list_log_files[]{"directory":"logs"}</function>
    Returns (tool_name, args_dict) or None.
    """
    if not text:
        return None
    pattern = r'<function[=(](\w+)[)\[>]*>\s*(\{.*?\})\s*</function>'
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1), safe_parse_args(m.group(2))
    # Also catch malformed variant without closing tag
    pattern2 = r'<function[=(](\w+)[)\[>]*[^\{]*(\{[^}]+\})'
    m2 = re.search(pattern2, text, re.DOTALL)
    if m2:
        return m2.group(1), safe_parse_args(m2.group(2))
    return None


# ── Tool execution ───────────────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_args: dict) -> str:
    if tool_args.get("_parse_error"):
        return f"Skipped '{tool_name}' — could not parse arguments."
    if tool_name not in TOOL_FUNCTIONS:
        return f"ERROR: Unknown tool '{tool_name}'"
    print(f"\n  {tool_name}({', '.join(f'{k}={str(v)[:60]}' for k,v in tool_args.items())})")
    try:
        result = TOOL_FUNCTIONS[tool_name](**tool_args)
        print(f"      {str(result)[:200]}")
        return str(result)
    except Exception as e:
        msg = f"Tool error in '{tool_name}': {type(e).__name__}: {e}"
        print(f"      {msg}")
        return msg


# ── Report saving ────────────────────────────────────────────────────────────

def save_final_report(content: str, label: str) -> str:
    from datetime import datetime
    filename = f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    saved_path = write_bug_report(filename, content)
    print(f"\n   Report saved  {saved_path}")
    return saved_path


# ── Main agent loop ──────────────────────────────────────────────────────────

def run_agent(user_goal: str, report_label: str = "bug_report", max_iterations: int = 15) -> str:
    print("\n" + "="*60)
    print(" AGENT START")
    print(f"Goal: {user_goal[:200]}")
    print("="*60)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_goal},
    ]

    final_text_parts = []
    iteration = 0

    # FIX: use a LOCAL variable so Python doesn't treat MODEL as unbound local
    current_model = MODELS[0]
    model_idx = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration}/{max_iterations} | model: {current_model} ---")

        # ── Call the LLM ────────────────────────────────────────────────────
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=False,
                max_tokens=4096,
            )

        except Exception as e:
            err = str(e)
            print(f"    Groq error: {err[:300]}")

            # Auto-switch if model is decommissioned
            if "decommissioned" in err or "model_decommissioned" in err:
                model_idx += 1
                if model_idx < len(MODELS):
                    current_model = MODELS[model_idx]
                    print(f"   Switching model  {current_model}")
                    continue
                else:
                    return "All fallback models are decommissioned. Check https://console.groq.com/docs/models"

            # On tool_use_failed, retry without tools to get plain text
            if "tool_use_failed" in err or "400" in err:
                print("   tool_use_failed — retrying as plain text...")
                try:
                    recovery = client.chat.completions.create(
                        model=current_model,
                        messages=messages + [{
                            "role": "user",
                            "content": "A tool call failed due to formatting. Provide your complete analysis as plain markdown text, no tool calls."
                        }],
                        max_tokens=4096,
                    )
                    text = recovery.choices[0].message.content or ""
                    final_text_parts.append(text)
                    save_final_report("\n\n".join(final_text_parts), report_label)
                    return text
                except Exception as e2:
                    print(f"   Recovery failed: {e2}")
                    return "Analysis incomplete due to repeated API errors."

            raise  # Re-raise anything unexpected

        # ── Process response ────────────────────────────────────────────────
        choice = response.choices[0]
        msg    = choice.message

        print(f"  finish_reason: {choice.finish_reason}")
        if msg.content:
            print(f"  text: {msg.content[:200].replace(chr(10),' ')}...")

        # Append to history
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        # Case 1 — proper tool calls via API
        if msg.tool_calls:
            for tc in msg.tool_calls:
                result = execute_tool(tc.function.name, safe_parse_args(tc.function.arguments))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        # Case 2 — LLM printed <function=...> as plain text
        inline = detect_inline_function_call(msg.content or "")
        if inline:
            tool_name, args = inline
            print(f"    Inline text tool call detected: {tool_name}")
            if tool_name == "write_bug_report":
                analysis = "\n\n".join(final_text_parts) or (msg.content or "")
                save_final_report(analysis, report_label)
                return analysis
            result = execute_tool(tool_name, args)
            messages.append({"role": "user", "content": f"[Tool result for {tool_name}]: {result}"})
            continue

        # Case 3 — LLM finished, capture final text
        final_content = msg.content or ""
        if final_content.strip():
            final_text_parts.append(final_content)
        full_report = "\n\n".join(final_text_parts)
        if full_report.strip():
            save_final_report(full_report, report_label)
        print("\n Agent done")
        return full_report

    # Max iterations safety net
    print("\n  Max iterations reached")
    fallback = "\n\n".join(final_text_parts)
    if fallback.strip():
        save_final_report(fallback, report_label + "_partial")
    return fallback or "No output collected."


if __name__ == "__main__":
    result = run_agent(
        user_goal="Analyze the Java application logs in 'logs/' — find bugs, performance issues, write a full bug report.",
        report_label="bug_report",
    )
    print("\n" + "="*60)
    print("FINAL REPORT:")
    print("="*60)
    print(result)