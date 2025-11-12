# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Heckler** is a live coding performance system that generates real-time LLM commentary on SuperCollider code evaluation. The LLM acts as a snarky but educational co-performer, providing commentary, explanations, and memes displayed alongside the live code.

## Core Architecture

### Multi-Component System

The system spans two laptops with these components:

1. **SuperCollider (Laptop 1)** - Audio synthesis + code capture via preprocessor
2. **Python Middleware (Laptop 1)** - Context management, Ollama communication, meme generation
3. **Ollama LLM (Laptop 2)** - Local LLM server (llama3.1:8b or mistral:7b)
4. **Browser Display (Laptop 1)** - WebSocket-based UI for LLM responses and memes

### Data Flow

```
SuperCollider evaluates code
    ↓ (OSC/HTTP)
Python middleware
    ↓ (HTTP POST to port 11434)
Ollama LLM
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

Ollama's structured JSON output (via `format` and `schema` parameters) ensures correct template selection and argument formatting.

## Communication Protocols

### SuperCollider to Python
- OSC (port 5000) or HTTP POST
- Sends evaluated code blocks via preprocessor hook

### Python to Ollama
- HTTP POST to `http://gaming-laptop-ip:11434/api/generate`
- Uses structured JSON schema for response format control

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

This is a simple repository with two fully independent components that communicate only at runtime:

```
heckler/
├── backend/                 # Python FastAPI server
│   ├── pyproject.toml      # Python dependencies (uv)
│   ├── uv.lock             # Python lockfile
│   ├── .venv/              # Python virtual environment
│   └── heckler/            # Python package
│       ├── __init__.py
│       ├── main.py         # FastAPI app entry point
│       ├── websocket.py    # WebSocket connection handlers
│       ├── llm.py          # Ollama integration + context management
│       ├── memes.py        # MemePy meme generation
│       └── osc_handler.py  # SuperCollider OSC/HTTP receiver
│
└── frontend/               # React + Vite browser UI
    ├── package.json        # JavaScript dependencies (pnpm)
    ├── pnpm-lock.yaml      # JavaScript lockfile
    └── src/
        ├── App.tsx
        ├── index.html
        ├── components/
        │   ├── LLMDisplay.tsx
        │   └── MemeDisplay.tsx
        └── hooks/
            └── useWebSocket.ts
```

### Component Separation
- Backend and frontend are **completely independent** and self-contained
- Each has its own dependency management (backend: uv, frontend: pnpm)
- No root-level configuration files needed
- They communicate only at runtime via WebSocket (backend port 8000, frontend port 5173)
- SuperCollider (external) sends code blocks to backend via OSC/HTTP

## Development Setup

### Tooling

**Python (Backend)**
- **uv**: Modern Python package manager (10-100x faster than pip/Poetry)
- **pyproject.toml**: Dependency management and project configuration
- **uvicorn**: ASGI server for FastAPI with hot reload

**JavaScript (Frontend)**
- **pnpm**: Fast, disk-efficient package manager
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
```

### Development Workflow

**Terminal 1 (Backend):**
```bash
cd backend
uv run uvicorn heckler.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
pnpm dev
```

**Ports:**
- Backend (FastAPI + WebSocket): `http://localhost:8000`
- Frontend (Vite): `http://localhost:5173`
- WebSocket endpoint: `ws://localhost:8000/ws`

### VSCode Tasks (Optional)

VSCode tasks can be configured in `.vscode/tasks.json` to easily start/stop/restart dev servers with keyboard shortcuts.

## Development Notes

### Context Window Management
The most critical technical challenge is managing LLM context without overwhelming the token limit while maintaining musical coherence. The system must balance:
- Recency (last few evaluations in detail)
- Salience (important moments persist)
- Compression (older material summarized)

### Why Local LLM
- Performance safety (no internet dependency during live performance)
- Low latency
- Complete control over prompts and context
- No API costs or rate limits

### Why Python Middleware
- Superior HTTP/async libraries compared to SuperCollider
- Easier context management experimentation
- MemePy integration for professional meme generation
- Separation of audio and AI logic

### MemePy Library
The project uses MemePy for meme generation. If additional customization is needed beyond the built-in 23+ templates, the library can be forked and modified. MemePy uses PIL internally and supports custom templates via external resource directories (ImageLibrary, MemeLibrary, FontLibrary).

### Live Coding Philosophy
The system reacts to **evaluated blocks** not keystroke tracking, maintaining live coding's evaluation-based workflow and creating better call-and-response rhythm with the LLM.

## Future Tooling Options

### mise (Maybe-Someday Option)
**mise** is a Rust-based polyglot task runner that could replace the two-terminal workflow with unified task orchestration:
- Single command (`mise run dev`) to start both servers with colored, prefixed output
- Could manage Python and Node.js versions, but maybe Docker is preferred for reproducibility
- Built-in parallel execution with process management
- TOML configuration similar to pyproject.toml

**When to consider:** If managing multiple services becomes cumbersome, or if we need coordinated startup/shutdown sequences.
