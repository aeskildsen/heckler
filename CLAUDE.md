# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Heckler** is a live coding performance system that generates real-time LLM commentary on SuperCollider code evaluation. The LLM acts as a snarky but educational co-performer, providing commentary, explanations, and memes displayed alongside the live code.

## Core Architecture

### Multi-Component System

1. **SuperCollider** - Audio synthesis + code capture via preprocessor
2. **Python Middleware** - Context management, LLM communication, meme generation
3. **LLM Backend** (one of three, configured in `config.yaml`):
   - `claude` — Anthropic Claude API (cloud, best quality)
   - `ollama_local` — Ollama on this machine with a small CPU model
   - `ollama_remote` — Ollama on a remote machine (gaming laptop) over LAN
4. **Browser Display** - WebSocket-based UI for LLM responses and memes

### Data Flow

```
SuperCollider evaluates code
    ↓ (OSC/HTTP)
Python middleware
    ↓ (Anthropic API  OR  HTTP POST to Ollama :11434)
LLM backend
    ↓ (HTTP response)
Python middleware
    ↓ (WebSocket)
Browser display
```

## Key Design Principles

### Temporal Awareness
The LLM context management must mirror musical perception:
- Recent evaluations should be clear and detailed
- Older material should be compressed/summarized
- Important musical "moments" (new Ndefs, structural changes, big parameter jumps) should persist longer
- Implements **sliding window context** with **salience markers** for important events

### Memory Strategy
- **Weighted context**: Recent blocks get full text, older ones compressed
- **Hidden summaries**: Periodic "private" LLM requests that compress musical trajectory (not displayed to audience)
- **Salience markers**: Flag important evaluations for longer retention
- **Sliding window**: Keep last 5-10 exchanges in detail

### Request Types
The system uses two types of LLM requests:
- **Public requests**: Displayed to audience (commentary, memes)
- **Private requests**: For context building/summarization (not displayed)

## Meme System Architecture

Uses **MemePy** (Python meme generator library) for professional meme generation with local templates.

### MemePy Integration
- **Library**: `MemePy` (pip installable, can be forked if needed for customization)
- **Template storage**: Local .png images in ImageLibrary directory (performance-safe, no internet dependency)
- **Template definitions**: JSON files in MemeLibrary directory defining text positions and arguments
- **Font support**: Custom fonts in FontLibrary directory for consistent styling
- **Built-in templates**: 23+ classic memes (Distracted Boyfriend, Drake, Two Buttons, etc.)
- **Custom templates**: Add via `add_external_resource_dir()` without modifying package

### MemePy API Usage
Python middleware uses these key functions:
- `get_meme_image_bytes(template, args)` - Returns BytesIO object for direct WebSocket transmission
- `get_meme_image(template, args)` - Returns PIL Image object for further processing
- `save_meme_to_disk(template, path, args)` - Saves generated memes for post-performance sharing

### LLM Output Format
```json
{
  "response_type": "meme",
  "template": "Balloon",
  "args": ["me", "actual musical structure", "{ LFNoise0.ar(8) }.poll;"],
  "caption": "Optional text displayed separately"
}
```

The LLM must know available MemePy template names and their argument counts:
- **2 args**: MeAlsoMe, ItsTime, Classy, Cola, Cliff, Knight, Vape, ButGodSaid
- **1 arg**: ItsRetarded, Headache, ClassNote, NutButton, Pills, Loud, Milk, Finally, Hate, Trump
- **3 args**: Balloon, PredatorHandshake, BellCurve

Ollama uses `format` + JSON schema for structured output. Claude uses tool use with a flat `input_schema` (Claude does not support `oneOf` at the top level of a tool schema). Both paths produce the same `Response` TypedDict.

## Communication Protocols

### SuperCollider to Python
- OSC (port 5005) or HTTP POST
- Sends evaluated code blocks via preprocessor hook

### Python to LLM
- **Claude**: Anthropic Python SDK (`anthropic.AsyncAnthropic`), reads `ANTHROPIC_API_KEY` from `.env` or environment
- **Ollama**: HTTP POST to `http://<host>:11434/api/generate` with JSON schema format field

### Python to Browser
- WebSocket (port 8765)
- Sends text responses and meme data

## Performance Layout

Screen is divided:
- **Left 2/3**: SuperCollider code editor
- **Right upper**: LLM responses and inline memes
- **Right middle**: Post window
- **Right lower**: Audio oscilloscope

## Repository Structure

```
heckler/
├── config.yaml             # Single config file for all settings
├── .env                    # API keys (gitignored, copy from .env.example)
├── .env.example            # Template for .env
├── start.sh                # One-line launcher: exec uv run --directory backend python start.py
├── list_models.py          # Helper: list available Claude models
│
├── backend/                # Python backend
│   ├── pyproject.toml      # Python dependencies (uv)
│   ├── uv.lock
│   ├── start.py            # Startup orchestrator (reads config, spawns services)
│   └── heckler/            # Python package
│       ├── app.py          # Main app: wires OSC → LLM → WebSocket
│       ├── config.py       # Config loader (config.yaml + .env)
│       ├── llm.py          # Multi-backend LLM client (Claude + Ollama)
│       ├── memes.py        # MemePy meme generation
│       ├── websocket.py    # WebSocket broadcaster
│       └── osc_server.py   # SuperCollider OSC/HTTP receiver
│
└── frontend/               # React + Vite browser UI
    ├── package.json
    └── src/
        ├── App.tsx
        ├── components/
        │   ├── LLMDisplay.tsx
        │   └── MemeDisplay.tsx
        └── hooks/
            └── useWebSocket.ts
```

### Component Separation
- Backend and frontend are **completely independent** and self-contained
- Each has its own dependency management (backend: uv, frontend: pnpm)
- Shared config lives in root `config.yaml` (read only by the backend at startup)
- They communicate only at runtime via WebSocket
- SuperCollider (external) sends code blocks to backend via OSC/HTTP

## Development Setup

### Tooling

**Python (Backend)**
- **uv**: Modern Python package manager (10-100x faster than pip/Poetry)
- **pyproject.toml**: Dependency management and project configuration
- **uvicorn**: ASGI server for FastAPI with hot reload

**JavaScript (Frontend)**
- **npm**: Fast, disk-efficient package manager
- **Vite**: Lightning-fast dev server with HMR (Hot Module Replacement)
- **React + TypeScript**: UI framework

**Task Running**
- Two separate terminals (or VSCode tasks) for backend and frontend dev servers
- No unified task orchestration initially (can be added later if needed)

### Initial Setup

```bash
# Python backend setup
cd backend
uv sync                      # Install Python dependencies

# Frontend setup
cd frontend
pnpm install                 # Install JavaScript dependencies

# API key (for Claude backend)
cp .env.example .env         # then edit .env
```

### Running

**All-in-one (production/performance):**
```bash
./start.sh
```
Reads `config.yaml` and starts backend + optionally frontend + browser. Handles nmcli for `ollama_remote`.

**Development (two terminals with hot reload):**

Terminal 1:
```bash
cd backend
uv run python -m heckler.app
```

Terminal 2:
```bash
cd frontend
pnpm dev
```

**Ports:**
- Backend (WebSocket): `ws://localhost:8765`
- Frontend (Vite): `http://localhost:5173`

### VSCode Tasks (Optional)

VSCode tasks can be configured in `.vscode/tasks.json` to easily start/stop/restart dev servers with keyboard shortcuts.

## Development Notes

### Context Window Management
The most critical technical challenge is managing LLM context without overwhelming the token limit while maintaining musical coherence. The system must balance:
- Recency (last few evaluations in detail)
- Salience (important moments persist)
- Compression (older material summarized)

### LLM Backend Choice
- **Claude API**: Highest quality, requires internet + API key, costs money per request
- **Ollama local**: No internet dependency, no cost, runs on CPU with small models (3b)
- **Ollama remote**: Best local quality (7b+ models) but requires lugging the gaming laptop

### Why Python Middleware
- Superior HTTP/async libraries compared to SuperCollider
- Easier context management experimentation
- MemePy integration for professional meme generation
- Separation of audio and AI logic

### MemePy Library
The project uses MemePy for meme generation. If additional customization is needed beyond the built-in 23+ templates, the library can be forked and modified. MemePy uses PIL internally and supports custom templates via external resource directories (ImageLibrary, MemeLibrary, FontLibrary).

### Live Coding Philosophy
The system reacts to **evaluated blocks** not keystroke tracking, maintaining live coding's evaluation-based workflow and creating better call-and-response rhythm with the LLM.

## Configuration Reference

All settings live in `config.yaml` at the project root:

| Section | Key | Description |
|---|---|---|
| `llm_backend` | — | `claude`, `ollama_remote`, or `ollama_local` |
| `ollama` | `host`, `port`, `model` | Remote Ollama server |
| `ollama_local` | `host`, `port`, `model` | Local Ollama (default: `qwen2.5-coder:3b`) |
| `claude` | `model` | Claude model ID (e.g. `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`) |
| `osc` | `host`, `port` | OSC receiver for SuperCollider |
| `websocket` | `host`, `port` | WebSocket server for the browser |
| `startup` | `frontend`, `browser`, `browser_cmd`, `network_profile` | What `start.sh` launches |
| `memes` | `enabled`, `min_interval`, `max_interval`, … | Meme generation settings |

API keys go in `.env` (gitignored), not in `config.yaml`.
