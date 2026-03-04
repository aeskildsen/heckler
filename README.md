# heckler

Infrastructure for LLM-generated commentary on live coding.

## LLM Backends

Configure `llm_backend` in `config.yaml`:

| Value | Description |
|---|---|
| `claude` | Anthropic Claude API — best quality, requires internet + API key |
| `ollama_local` | Ollama on this machine with a small CPU-friendly model (`qwen2.5-coder:3b`) |
| `ollama_remote` | Ollama on the gaming laptop over a direct LAN link |

### Claude setup

Add your API key to `.env` in the project root (gitignored):

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

Model is set in `config.yaml` under `claude.model`. Use `claude-haiku-4-5-20251001` (fast/cheap) or `claude-sonnet-4-6` (higher quality).

To list available models:

```bash
uv run --directory backend python list_models.py
```

### Local Ollama setup

```bash
ollama pull qwen2.5-coder:3b
# set llm_backend: ollama_local in config.yaml
```

### Remote Ollama (gaming laptop) setup

Ensure the ethernet adapter has a static IP configured on the Windows machine:
- IP address: `192.168.137.1` / Subnet: `255.255.255.0` / Gateway: blank

Ollama must listen on all interfaces — set `OLLAMA_HOST=0.0.0.0` and restart Ollama.

Test connectivity:
```bash
ping 192.168.137.1
curl http://192.168.137.1:11434/api/tags
```

## Pre-performance Setup

### 1. Configure `config.yaml`

Set your desired `llm_backend` and check the `startup` section:

```yaml
startup:
  frontend: true         # Start the Vite dev server
  browser: true          # Open Chromium at localhost:5173
  browser_cmd: "chromium-browser"
  network_profile: "direct-link"  # nmcli profile (ollama_remote only)
```

### 2. Audio Routing (headphone output for Reaper)

By default, PipeWire uses the Speaker profile. Switch to Headphones:

```bash
pactl set-card-profile alsa_card.pci-0000_00_1f.3-platform-skl_hda_dsp_generic "HiFi (HDMI1, HDMI2, HDMI3, Headphones, Mic1, Mic2)"
```

Then use `qpwgraph` to route SuperCollider → Reaper → Headphones.

### 3. Start Heckler

```bash
./start.sh
```

This reads `config.yaml` and starts the backend, optionally the frontend, and optionally opens the browser. If `llm_backend` is `ollama_remote` it also brings up the `direct-link` nmcli profile automatically.

### 4. Run launch script in sc-livecode

```bash
./launch.sh
```

Launches windows and virtual desktops in sway.

## Layout

```
┌─────────────────────┬──────────┐
│                     │   LLM    │
│   SuperCollider     │ responses│
│      Code           │  +memes  │
│      Editor         ├──────────┤
│     (2/3 width)     │   Post   │
│                     │  Window  │
│                     ├──────────┤
│                     │  Scope   │
└─────────────────────┴──────────┘
```
