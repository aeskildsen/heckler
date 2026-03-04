# heckler

Infrastructure for LLM-generated commentary on live coding

## Pre-performance Setup

### 1. Network Connection (direct link to Ollama machine)

Connect the USB ethernet adapter to the same USB port as configured, then:

```bash
nmcli con up direct-link
```

Verify connectivity:
```bash
ping 192.168.137.1
```

### 2. Windows Machine (Ollama host)

Ensure the ethernet adapter has a static IP configured:
- IP address: `192.168.137.1`
- Subnet mask: `255.255.255.0`
- Gateway/DNS: leave blank

Ollama must listen on all interfaces. Set environment variable `OLLAMA_HOST=0.0.0.0` and restart Ollama.

Test from Linux machine:
```bash
curl http://192.168.137.1:11434/api/tags
```

### 3. Audio Routing (headphone output for Reaper)

By default, PipeWire uses the Speaker profile. Switch to Headphones:

```bash
pactl set-card-profile alsa_card.pci-0000_00_1f.3-platform-skl_hda_dsp_generic "HiFi (HDMI1, HDMI2, HDMI3, Headphones, Mic1, Mic2)"
```

Then use `qpwgraph` to route SuperCollider → Reaper → Headphones.

### 4. Start Heckler

```bash
./start_local.sh
```

This starts the backend, frontend, and opens the browser display.

### 5. Run launch script in sc-livecode

./launch.sh

Launches winows and virtual desktops in sway

## Layout diagram

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