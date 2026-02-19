# Java Bug Analysis — Agentic AI Pipeline

A complete project where a **Groq-powered AI agent** analyzes Java application logs
and profiler output to generate bug reports with suggested fixes.

---

## Project Structure

```
java_agent_project/
│
├── Java Side (generates the data)
│   ├── TestApp.java        ← Simulated Java app with intentional bugs
│   └── Profiler.java       ← JVM profiler that writes metrics to file
│
├── Python Agent Side (analyzes the data)
│   ├── agent_tools.py      ← PART 1: Tool definitions (what the agent CAN do)
│   ├── agent_loop.py       ← PART 2: The agent loop (how it THINKS and ACTS)
│   └── pipeline.py         ← PART 3: The orchestrator (how it all fits together)
│
└── Generated at runtime
    ├── logs/app.log         ← Java app output
    ├── logs/profiler.log    ← JVM metrics output
    └── reports/*.md         ← Agent-generated bug reports
```

---

## How It Works (Agentic vs RAG)

```
RAG:   User query → retrieve docs → LLM answers → DONE
                    (one shot, passive)

Agent: User goal → LLM decides what tool to call
                 → Executes tool (e.g., read_log_file)
                 → LLM sees result, decides next tool
                 → Executes tool (e.g., search_log_patterns)
                 → LLM sees result, decides next tool
                 → ... (loops until task complete)
                 → Calls write_bug_report
                 → DONE
```

The key difference: **the LLM is in control of what to do and in what order.**

---

## Quick Start

### Step 1: Install Python dependencies
```bash
pip install groq
```

### Step 2: Get your free Groq API key
- Go to: https://console.groq.com
- Sign up (free)
- Create an API key
- Export it:
```bash
export GROQ_API_KEY="your_key_here"
```

### Step 3: Generate logs (optional — pipeline auto-creates demo logs)
```bash
# Compile and run Java app
javac -d ./bin -cp ./src ./src/TestApp.java
java -cp ./bin TestApp

# In another terminal, run profiler simultaneously
javac -d ./bin -cp ./src ./src/Profiler.java && java -cp ./bin Profiler
```

### Step 4: Run the agent pipeline
```bash
python pipeline.py
```

The agent will:
1. Discover log files
2. Summarize statistics
3. Search for specific errors
4. Cross-reference app errors with profiler data
5. Write a full bug report to `reports/`

---

## File-by-File Breakdown

### `TestApp.java` — The broken Java app
Simulates a real app with:
- **PaymentModule**: Has NullPointerException bugs (no null check after DB query)
- **DatabaseModule**: Simulates timeouts, slow queries
- **CacheModule**: Unbounded growth → memory pressure
- Logs everything to `logs/app.log`

### `Profiler.java` — The JVM profiler
Uses Java's built-in `ManagementFactory` to capture:
| Metric | JVM Equivalent of... |
|--------|----------------------|
| Heap usage | RAM usage |
| Minor GC | Page reads (fast, frequent) |
| Major GC | Page writes/evictions (slow, expensive) |
| GC pause time | Page miss penalty |
| Thread deadlocks | System deadlock |
Writes to `logs/profiler.log` every 2 seconds.

### `agent_tools.py` — The agent's hands
Defines 5 tools the LLM can call:
| Tool | What it does |
|------|-------------|
| `list_log_files` | Discover available logs |
| `summarize_log_stats` | Get error counts, top errors, time range |
| `read_log_file` | Read raw log content |
| `search_log_patterns` | Regex search with context lines |
| `write_bug_report` | Save final report to disk |

### `agent_loop.py` — The agent's brain
The **agentic loop**:
```
while not done:
    response = ask_groq(messages, tools)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
            messages.append(result)  # LLM sees the result
    else:
        return response.text  # Done!
```

### `pipeline.py` — The orchestrator
Two modes:
- **Single-pass**: One agent session does everything
- **Multi-pass**: Three specialized sessions
  - Pass 1: Error analysis
  - Pass 2: Performance analysis
  - Pass 3: Synthesis into one final report

---

## Example Output

The agent produces a markdown report like:

```markdown
# Bug Report — Java Application Analysis

## Executive Summary
3 critical bugs found. NullPointerException in PaymentModule (9 occurrences)
correlates with cache misses causing unbounded heap growth, leading to
major GC pauses of 380-520ms disrupting service.

## Critical Bugs (P1)

### Bug 1: NullPointerException in PaymentModule
**Evidence**: [2024-01-15 10:00:03] [ERROR] Null account data...
**Root Cause**: No null check after DatabaseModule.query()
**Fix**:
    String result = DatabaseModule.query(sql);
    if (result == null) {
        log("WARN", "PaymentModule", "No account found, returning early");
        return;  // ← Add this
    }

## Performance Issues (P2)

### Issue 1: Unbounded Cache Growth → GC Pressure
**Evidence**: Heap 93.7% at 10:00:06, GC pause 520ms
**Root Cause**: CacheModule.cache list grows without bound
**Fix**: Use LinkedHashMap with max size (LRU cache)
```

---

## Customization

**Change the model** in `agent_loop.py`:
```python
MODEL = "llama-3.3-70b-versatile"   # Best quality (default)
MODEL = "llama-3.1-8b-instant"      # Faster, lighter
MODEL = "mixtral-8x7b-32768"        # Large context window
```

**Add new tools** in `agent_tools.py`:
```python
def my_new_tool(param: str) -> str:
    # do something
    return result

# Add to TOOLS list and TOOL_FUNCTIONS dict
```

**Switch from multi-pass to single-pass** in `pipeline.py`:
```python
CONFIG = {
    "multi_pass": False,  # ← change this
}
```
