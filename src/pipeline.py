"""
pipeline.py
===========
PART 3: The Bug Report Pipeline
--------------------------------
This is the top-level orchestrator that:
  1. Lets you configure what to analyze
  2. Runs the agent with a well-crafted goal
  3. Optionally runs multiple passes (e.g., first analyze errors,
     then analyze performance, then combine into one report)

This is the file you RUN to kick off the whole system.

Usage:
  python pipeline.py

Requirements:
  pip install groq
  export GROQ_API_KEY="your_key_here"   # get free at console.groq.com
"""

import os
import json
from datetime import datetime
from agent_loop import run_agent


# -------------------------------------------------------
# PART 3A: Pipeline configuration
# Tweak these to control what the agent analyzes
# -------------------------------------------------------
CONFIG = {
    "app_log": "logs/app.log",
    "profiler_log": "logs/profiler.log",
    "output_report": f"bug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
    
    # Run multi-pass analysis? (more thorough but more API calls)
    "multi_pass": True,
}


# -------------------------------------------------------
# PART 3B: Single-pass pipeline
# One agent call that does everything
# -------------------------------------------------------
def run_single_pass():
    """One agent session: analyze everything and write a report."""
    
    goal = f"""
    You are analyzing a Java application for bugs and performance issues.
    
    Available log files:
    - App log (errors, warnings, execution states): {CONFIG['app_log']}
    - Profiler log (memory, GC, threads, CPU): {CONFIG['profiler_log']}
    
    Please:
    1. List available log files
    2. Get statistics for both logs
    3. Find all ERROR and WARN entries in the app log
    4. Find any GC_ALERT or DEADLOCK_ALERT in the profiler log
    5. Search for NullPointerException and other specific exceptions
    6. Cross-reference: do memory/GC spikes coincide with errors?
    7. Write a complete bug report to: {CONFIG['output_report']}
    
    The bug report must include:
    - Executive Summary
    - Critical Bugs (with exact log evidence)
    - Performance Issues (from profiler)
    - Root Cause Analysis
    - Suggested Code Fixes (with code snippets)
    - Priority ranking (P1/P2/P3)
    """
    
    return run_agent(goal, report_label="bug_report")


# -------------------------------------------------------
# PART 3C: Multi-pass pipeline
# Agent runs in specialized phases — more thorough
# -------------------------------------------------------
def run_multi_pass():
    """
    Three focused agent passes:
    Pass 1: Error analysis (app.log)
    Pass 2: Performance analysis (profiler.log)  
    Pass 3: Synthesis — combine findings into one report
    """
    
    print("\n PASS 1: Error Analysis")
    print("-" * 40)
    
    pass1_goal = f"""
    Focus ONLY on error analysis. Analyze: {CONFIG['app_log']}
    
    1. List log files in the logs/ directory
    2. Get statistics for {CONFIG['app_log']}
    3. Find all ERROR entries and categorize them by type
    4. Find NullPointerException instances and their context
    5. Find any database failures, timeouts, or connection errors
    6. Find any "Unhandled state" messages
    7. Save a focused error report to: reports/pass1_errors.md
    
    Include exact log lines as evidence for each bug found.
    """
    pass1_result = run_agent(pass1_goal, report_label="pass1_errors", max_iterations=8)
    
    print("\n PASS 2: Performance Analysis")
    print("-" * 40)
    
    pass2_goal = f"""
    Focus ONLY on performance analysis. Analyze: {CONFIG['profiler_log']}
    
    1. Get statistics for {CONFIG['profiler_log']}
    2. Find all GC_ALERT entries (high GC pause times)
    3. Look for high heap usage (>80% utilization)
    4. Find any DEADLOCK_ALERT entries
    5. Look for high CPU usage patterns
    6. Check for memory pool issues (Old Gen filling up)
    7. Save a focused performance report to: reports/pass2_performance.md
    
    Identify specific time ranges where performance degraded.
    """
    pass2_result = run_agent(pass2_goal, report_label="pass2_performance", max_iterations=8)
    
    print("\n PASS 3: Synthesis Report")
    print("-" * 40)
    
    pass3_goal = f"""
    Read the two analysis reports:
    - reports/pass1_errors.md  (error analysis)
    - reports/pass2_performance.md  (performance analysis)
    
    Synthesize them into one final, comprehensive bug report.
    
    The final report at reports/{CONFIG['output_report']} must include:
    
    # Bug Report — Java Application Analysis
    
    ## Executive Summary
    (2-3 sentence overview of what's wrong)
    
    ## Critical Bugs (P1)
    (Bugs that cause failures or data loss — with log evidence and code fix)
    
    ## Performance Issues (P2)
    (Memory leaks, GC pressure, slow queries — with profiler evidence)
    
    ## Warnings & Tech Debt (P3)
    (Things to fix before they become P1)
    
    ## Root Cause Analysis
    (Why are these happening? e.g., missing null checks, unbounded cache)
    
    ## Suggested Code Fixes
    (Actual Java code snippets for each bug)
    
    ## Correlation Analysis
    (Do GC spikes happen at the same time as errors? Show the evidence.)
    
    ## Fix Priority & Effort Matrix
    | Bug | Priority | Estimated Fix Time |
    
    Save to: reports/{CONFIG['output_report']}
    """
    pass3_result = run_agent(pass3_goal, report_label="pass3_final_report", max_iterations=8)
    
    return pass3_result


# -------------------------------------------------------
# PART 3D: Main entry point
# -------------------------------------------------------
def main():
    print("="*60)
    print(" JAVA BUG ANALYSIS PIPELINE")
    print("="*60)
    
    # Check API key
    if not os.environ.get("GROQ_API_KEY"):
        print("\n ERROR: GROQ_API_KEY not set!")
        print("Get your free key at: https://console.groq.com")
        print("Then run: export GROQ_API_KEY='your_key_here'")
        return
    
    # Check that log files exist (or create demo ones)
    if not os.path.exists("logs"):
        print("\n  No 'logs/' directory found.")
        print("Run TestApp.java and Profiler.java first to generate logs.")
        # print("Creating demo log files for testing...\n")
        # create_demo_logs()
    
    # Run the pipeline
    if CONFIG["multi_pass"]:
        print("\nRunning MULTI-PASS analysis (more thorough)...")
        result = run_multi_pass()
    else:
        print("\nRunning SINGLE-PASS analysis...")
        result = run_single_pass()
    
    print("\n" + "="*60)
    print(" PIPELINE COMPLETE")
    print(f" Report saved to: reports/{CONFIG['output_report']}")
    print("="*60)


# # -------------------------------------------------------
# # Demo log generator — creates fake logs for testing
# # without needing to compile/run Java
# # -------------------------------------------------------
# def create_demo_logs():
#     """Create realistic demo log files for testing the agent."""
#     import random
    
#     os.makedirs("logs", exist_ok=True)
    
#     # Demo app.log
#     with open("logs/app.log", "w") as f:
#         f.write("[2024-01-15 10:00:01.123] [INFO] [Main] === Application START ===\n")
#         f.write("[2024-01-15 10:00:02.456] [INFO] [DatabaseModule] Query OK (45ms) [query #1]: SELECT balance FROM accounts WHERE user='user_001'\n")
#         f.write("[2024-01-15 10:00:03.789] [ERROR] [PaymentModule] Null account data during payment processing | Exception: NullPointerException: Account balance result was null for user: user_404\n")
#         f.write("    STACKTRACE: java.lang.NullPointerException: Account balance result was null\n")
#         f.write("        at PaymentModule.processPayment(TestApp.java:87)\n")
#         f.write("        at TestApp.main(TestApp.java:142)\n")
#         f.write("[2024-01-15 10:00:05.001] [WARN] [DatabaseModule] Slow query detected (342ms): SELECT balance FROM accounts WHERE user='user_002'\n")
#         f.write("[2024-01-15 10:00:06.002] [ERROR] [PaymentModule] Payment failed for user=user_003 | Exception: RuntimeException: Connection timeout to DB after 3 retries\n")
#         f.write("[2024-01-15 10:00:08.003] [WARN] [PaymentModule] High-value transaction flagged for review: $12450.23\n")
#         f.write("[2024-01-15 10:00:10.004] [WARN] [CacheModule] Cache MISS for key=session:user_001 [hits=2 misses=8]\n")
#         f.write("[2024-01-15 10:00:12.005] [ERROR] [Main] Unhandled state reached! System may be in inconsistent state.\n")
#         f.write("[2024-01-15 10:00:15.006] [ERROR] [PaymentModule] Null account data during payment processing | Exception: NullPointerException: Account balance result was null for user: user_999\n")
#         f.write("[2024-01-15 10:00:30.007] [INFO] [Main] === Application SHUTDOWN ===\n")
    
#     # Demo profiler.log
#     with open("logs/profiler.log", "w") as f:
#         f.write("[2024-01-15 10:00:00.000] === PROFILER START | Sampling every 2s ===\n")
#         f.write("[2024-01-15 10:00:02.001] MEMORY | Heap Used: 128MB / 256MB (50.0%) | Committed: 256MB | Max: 512MB\n")
#         f.write("[2024-01-15 10:00:02.002] GC | MINOR_GC | G1 Young Generation | Total Collections: 5 | Total Time: 120ms | Delta Collections: 2 | Delta Time: 45ms\n")
#         f.write("[2024-01-15 10:00:02.003] THREADS | Active: 12 | Peak: 15 | Daemon: 8 | Total Started: 25\n")
#         f.write("[2024-01-15 10:00:04.001] MEMORY | Heap Used: 340MB / 512MB (66.4%) | Committed: 512MB | Max: 512MB\n")
#         f.write("[2024-01-15 10:00:04.002] GC_ALERT | High GC pause detected: 380ms in last interval for G1 Old Gen\n")
#         f.write("[2024-01-15 10:00:04.003] GC | MAJOR_GC | G1 Old Generation | Total Collections: 3 | Total Time: 890ms | Delta Collections: 1 | Delta Time: 380ms\n")
#         f.write("[2024-01-15 10:00:06.001] MEMORY | Heap Used: 480MB / 512MB (93.7%) | Committed: 512MB | Max: 512MB\n")
#         f.write("[2024-01-15 10:00:06.002] GC_ALERT | High GC pause detected: 520ms in last interval for G1 Old Gen\n")
#         f.write("[2024-01-15 10:00:06.003] MEMPOOL | G1 Old Gen              Used: 390144KB | Max: 512MB\n")
#         f.write("[2024-01-15 10:00:08.001] CPU | Available Processors: 8 | System Load Average: 3.45\n")
#         f.write("[2024-01-15 10:00:08.002] CPU | Process CPU Usage: 78.2% | System CPU Usage: 45.1%\n")
    
#     print(" Demo log files created in logs/")


if __name__ == "__main__":
    main()
