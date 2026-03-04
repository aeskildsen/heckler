#!/usr/bin/env python3
"""
Heckler startup script.

Reads config.yaml and starts the appropriate services:
  - nmcli network profile  (ollama_remote only)
  - Python backend
  - Vite frontend          (if startup.frontend: true)
  - Chromium browser       (if startup.browser: true)

Invoked via the root ./start.sh wrapper.
"""

import subprocess
import sys
import time
from pathlib import Path

from heckler.config import Config

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN = "\033[0;32m"
BLUE  = "\033[0;34m"
RED   = "\033[0;31m"
CYAN  = "\033[0;36m"
NC    = "\033[0m"

def info(msg):  print(f"{BLUE}{msg}{NC}")
def ok(msg):    print(f"{GREEN}✓ {msg}{NC}")
def err(msg):   print(f"{RED}✗ {msg}{NC}", file=sys.stderr)
def section(msg): print(f"\n{CYAN}── {msg} ──{NC}")

# ── Load config ───────────────────────────────────────────────────────────────
config = Config()
ROOT = Path(__file__).parent.parent  # project root

# ── Process registry ──────────────────────────────────────────────────────────
procs: list[subprocess.Popen] = []

def cleanup():
    section("Shutting down")
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    ok("All processes stopped")

import atexit, signal as _signal
atexit.register(cleanup)
_signal.signal(_signal.SIGTERM, lambda *_: sys.exit(0))

# ── Network (ollama_remote only) ──────────────────────────────────────────────
if config.llm_backend == "ollama_remote":
    profile = config.startup_network_profile
    section(f"Network: bringing up '{profile}'")
    result = subprocess.run(["nmcli", "con", "up", profile], capture_output=True, text=True)
    if result.returncode == 0:
        ok(f"Network profile '{profile}' is up")
    else:
        # Non-fatal — might already be connected
        err(f"nmcli returned non-zero (maybe already connected?): {result.stderr.strip()}")
else:
    info(f"LLM backend: {config.llm_backend!r} — skipping nmcli")

# ── Backend ───────────────────────────────────────────────────────────────────
section("Backend")
backend_proc = subprocess.Popen(
    ["uv", "run", "python", "-m", "heckler.app"],
    cwd=Path(__file__).parent,
)
procs.append(backend_proc)
ok(f"Backend started (pid {backend_proc.pid})")

# Give the backend a moment to bind its ports
time.sleep(2)

# ── Frontend ──────────────────────────────────────────────────────────────────
frontend_proc = None
if config.startup_frontend:
    section("Frontend")
    frontend_proc = subprocess.Popen(
        ["pnpm", "dev"],
        cwd=ROOT / "frontend",
    )
    procs.append(frontend_proc)
    ok(f"Frontend started (pid {frontend_proc.pid})")
    time.sleep(3)  # Let Vite finish its initial build

# ── Browser ───────────────────────────────────────────────────────────────────
if config.startup_browser and config.startup_frontend:
    section("Browser")
    cmd = config.startup_browser_cmd
    browser_proc = subprocess.Popen(
        [cmd, "--app=http://localhost:5173"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    procs.append(browser_proc)
    ok(f"Launched {cmd}")
elif config.startup_browser and not config.startup_frontend:
    err("startup.browser is true but startup.frontend is false — nothing to open")

# ── Summary ───────────────────────────────────────────────────────────────────
section("Heckler is running")
print(f"  LLM backend  : {config.llm_backend}")
print(f"  Backend      : http://localhost:8000")
if config.startup_frontend:
    print(f"  Frontend     : http://localhost:5173")
print()
print("Press Ctrl+C to stop all services")
print()

# ── Wait ──────────────────────────────────────────────────────────────────────
try:
    while True:
        # Exit if the backend dies unexpectedly
        if backend_proc.poll() is not None:
            err(f"Backend exited with code {backend_proc.returncode}")
            sys.exit(backend_proc.returncode)
        if frontend_proc and frontend_proc.poll() is not None:
            err(f"Frontend exited with code {frontend_proc.returncode}")
            sys.exit(frontend_proc.returncode)
        time.sleep(1)
except KeyboardInterrupt:
    print()  # newline after ^C
