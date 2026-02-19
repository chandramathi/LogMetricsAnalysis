"""
agent_tools.py
==============
PART 1: Tool Definitions

FIX NOTES (v2):
  - write_bug_report is REMOVED from the TOOLS list the LLM sees.
    Why: The LLM tried to stuff full markdown reports into JSON string args,
    which Groq rejects with 400 'tool_use_failed'. Instead, agent_loop.py
    intercepts the LLM's final text and saves it directly.
  - write_bug_report still exists as a Python function for agent_loop.py
    to call directly (not via the LLM).
  - Fixed double 'reports/reports/' path bug.
"""

import os
import re
from collections import defaultdict


# -------------------------------------------------------
# TOOL 1: List available log files
# -------------------------------------------------------
def list_log_files(directory: str = "logs") -> str:
    """List all log files in the given directory."""
    if not os.path.exists(directory):
        return f"Directory not found: {directory}"
    files = []
    for f in os.listdir(directory):
        full_path = os.path.join(directory, f)
        size_kb = os.path.getsize(full_path) / 1024
        files.append(f"  {f} ({size_kb:.1f} KB)")
    if not files:
        return "No log files found."
    return f"Log files in '{directory}':\n" + "\n".join(files)


# -------------------------------------------------------
# TOOL 2: Summarize log statistics
# -------------------------------------------------------
def summarize_log_stats(filepath: str) -> str:
    """Return counts of ERROR/WARN/INFO, top error messages, and time range."""
    if not os.path.exists(filepath):
        return f"ERROR: File not found: {filepath}"
    with open(filepath, "r") as f:
        lines = f.readlines()
    counts = defaultdict(int)
    error_messages = defaultdict(int)
    timestamps = []
    for line in lines:
        for level in ["ERROR", "WARN", "INFO", "DEBUG", "ALERT"]:
            if f"[{level}]" in line:
                counts[level] += 1
        if "[ERROR]" in line:
            parts = line.strip().split("]")
            if len(parts) >= 4:
                msg = parts[3][:80].strip()
                error_messages[msg] += 1
        ts_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
        if ts_match:
            timestamps.append(ts_match.group())
    top_errors = sorted(error_messages.items(), key=lambda x: -x[1])[:5]
    result = (
        f"\nLOG STATISTICS for {filepath}\n"
        f"================================\n"
        f"Total lines: {len(lines)}\n"
        f"Time range: {timestamps[0] if timestamps else 'N/A'} to "
        f"{timestamps[-1] if timestamps else 'N/A'}\n\n"
        f"Level Counts:\n"
        f"  ERROR : {counts['ERROR']}\n"
        f"  WARN  : {counts['WARN']}\n"
        f"  INFO  : {counts['INFO']}\n"
        f"  ALERT : {counts['ALERT']}\n\n"
        f"Top Error Messages:\n"
    )
    for msg, count in top_errors:
        result += f"  [{count}x] {msg}\n"
    return result


# -------------------------------------------------------
# TOOL 3: Read a log file
# -------------------------------------------------------
def read_log_file(filepath: str, max_lines: int = 200) -> str:
    """Read a log file and return its contents (last N lines)."""
    if not os.path.exists(filepath):
        return f"ERROR: File not found: {filepath}"
    with open(filepath, "r") as f:
        lines = f.readlines()
    selected = lines[-max_lines:] if len(lines) > max_lines else lines
    return f"[FILE: {filepath} | Lines: {len(selected)} of {len(lines)}]\n" + "".join(selected)


# -------------------------------------------------------
# TOOL 4: Search for patterns in a log file
# -------------------------------------------------------
def search_log_patterns(filepath: str, pattern: str, context_lines: int = 2) -> str:
    """Search for a regex pattern in a log file. Returns matching lines + context."""
    if not os.path.exists(filepath):
        return f"ERROR: File not found: {filepath}"
    with open(filepath, "r") as f:
        lines = f.readlines()
    results = []
    for i, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            block = lines[start:end]
            results.append(f"--- Match at line {i+1} ---\n" + "".join(block))
    if not results:
        return f"No matches found for pattern '{pattern}' in {filepath}"
    return f"Found {len(results)} match(es) for '{pattern}':\n\n" + "\n".join(results)


# -------------------------------------------------------
# TOOL 5: write_bug_report
# Called directly by agent_loop.py — NOT exposed to the LLM.
# This avoids the Groq 400 error from large JSON string arguments.
# -------------------------------------------------------
def write_bug_report(filename: str, content: str) -> str:
    """Write a bug report to the reports/ directory. Returns the saved filepath."""
    os.makedirs("reports", exist_ok=True)
    # Fix: strip any 'reports/' prefix the LLM may have added to avoid reports/reports/
    clean_name = filename.lstrip("/").lstrip("\\")
    if clean_name.lower().startswith("reports/") or clean_name.lower().startswith("reports\\"):
        clean_name = clean_name[8:]
    filepath = os.path.join("reports", clean_name)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


# -------------------------------------------------------
# TOOL REGISTRY — only tools the LLM is allowed to call.
# write_bug_report is intentionally NOT in this list.
# -------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_log_files",
            "description": "List all log files in a directory. Call this first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to scan", "default": "logs"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_log_stats",
            "description": "Get error counts, top errors, and time range for a log file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the log file, e.g. 'logs/app.log'"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_log_file",
            "description": "Read raw contents of a log file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the log file"},
                    "max_lines": {"type": "integer", "description": "Max lines to return (default 200)", "default": 200}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_log_patterns",
            "description": "Search for a regex pattern in a log file to find specific errors or events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the log file"},
                    "pattern": {"type": "string", "description": "Regex pattern, e.g. 'NullPointerException' or 'GC_ALERT'"},
                    "context_lines": {"type": "integer", "description": "Lines of context around matches (default 2)", "default": 2}
                },
                "required": ["filepath", "pattern"]
            }
        }
    }
]

TOOL_FUNCTIONS = {
    "list_log_files": list_log_files,
    "summarize_log_stats": summarize_log_stats,
    "read_log_file": read_log_file,
    "search_log_patterns": search_log_patterns,
}
