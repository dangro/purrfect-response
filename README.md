# claude-tts

Local text-to-speech using [KittenTTS](https://github.com/KittenML/KittenTTS) — a lightweight, CPU-optimized ONNX-based TTS library. No GPU required.

Includes a Claude Code integration that speaks every assistant response aloud via a persistent background daemon. The integration is a **Stop hook** (fires automatically after every response) plus two **slash commands** (`/stop-tts`, `/tts-set`) you invoke manually.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)
- `espeak-ng` system library (required by phonemizer)

### Install espeak-ng

**Ubuntu/Debian:**
```bash
sudo apt install espeak-ng
```

**macOS:**
```bash
brew install espeak-ng
```

**Windows (native):**
Download and install from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases).

**WSL2:**
```bash
sudo apt install espeak-ng
```
Audio playback on WSL2 uses Windows audio via PowerShell — no extra setup needed as long as WSLg is running (Windows 11).

## Setup

```bash
git clone <repo-url>
cd claude-tts
uv sync
```

`uv sync` installs all dependencies including the KittenTTS 0.8.1 wheel from the GitHub release. On first run, model weights (~80 MB for mini) are downloaded from Hugging Face and cached locally. After that, **no network calls are made** — the daemon loads exclusively from cache.

## Running the test script

```bash
uv run python test_tts.py
```

This downloads the model if needed and generates a set of `.wav` files:

| File | Description |
|------|-------------|
| `output.wav` | Basic generation with the Jasper voice |
| `output_speed_0.8.wav` | Luna voice at 0.8x speed |
| `output_speed_1.0.wav` | Luna voice at 1.0x speed (normal) |
| `output_speed_1.2.wav` | Luna voice at 1.2x speed |
| `output_<Voice>.wav` | One file per available voice |

## Claude Code integration

The integration has three parts: a background daemon, a Stop hook, and two slash commands.

### 1. Daemon (`tts_daemon.py`)

A persistent background process that keeps the ONNX model loaded in memory. Uses a two-stage pipeline — a generator thread synthesizes the next sentence while the player thread plays the current one — so long responses start playing immediately rather than waiting for full synthesis.

Start the daemon once per session:

```bash
nohup .venv/bin/python tts_daemon.py > /tmp/tts-daemon.log 2>&1 &
```

The daemon auto-starts if `speak.py` is called and the socket is missing.

To stop the daemon:

```bash
kill $(cat /tmp/claude-tts.pid)
```

To check whether it is running:

```bash
ls /tmp/claude-tts.sock && echo "running" || echo "not running"
```

Logs are written to `/tmp/tts-daemon.log`.

### 2. Hook (`speak.py`)

A Claude Code Stop hook — called automatically after every response. It processes text through several stages before sending to the daemon:

1. **Markdown stripping** — fenced code blocks become "code block.", inline code backticks are stripped (content kept), headers/bold/links are unwrapped, list items become period-terminated sentences.
2. **TTS normalization** — arrows become spoken words, URLs become "link", `snake_case` and `camelCase` are spaced out, common abbreviations (`e.g.`, `i.e.`, `etc.`) are expanded, known acronyms (`API`, `CLI`, `TTS`, etc.) have their letters spaced for correct pronunciation, filenames like `config.json` are read as "config dot json".
3. **Sentence splitting** — splits on sentence-ending punctuation and em-dashes.
4. **Character cap** — only the first N characters worth of sentences are sent (configurable in `config.json`, default 600), so long responses start playing quickly.

When a turn ends with a tool call rather than a text response, `last_assistant_message` is empty. In that case the hook falls back to reading the transcript JSONL at `transcript_path` and extracting the last assistant text block directly.

To skip TTS for a specific response, include `#notts` anywhere in your message. The hook reads the last user message from the transcript and silently exits if the tag is present.

The hook is configured in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/.venv/bin/python /path/to/speak.py >> /tmp/tts-speak.log 2>&1"
          }
        ]
      }
    ]
  }
}
```

Update the paths to match your install location, then restart Claude Code to reload.

### 3. Slash commands

**`/stop-tts`** — interrupts playback immediately and clears the queue. Can also be run directly:

```bash
.venv/bin/python stop_tts.py
```

Install by creating `~/.claude/commands/stop-tts.md` (update paths):

```markdown
Stop TTS playback immediately, clearing any queued audio.

!  /path/to/.venv/bin/python /path/to/stop_tts.py
```

**`/tts-set`** — updates voice, speed, model, or character limit without restarting the daemon. Changes take effect on the next spoken sentence.

```
/tts-set --voice Luna --speed 1.1
/tts-set --char-limit 800
/tts-set --model KittenML/kitten-tts-micro-0.8
```

Can also be run directly:

```bash
.venv/bin/python set_tts.py --voice Rosie --speed 0.9
```

Install by creating `~/.claude/commands/tts-set.md` (update paths):

```markdown
Update TTS parameters. Changes take effect on the next spoken sentence — no daemon restart needed.

Usage: /tts-set --voice Luna --speed 1.1 --char-limit 800

Available voices: Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo

! /path/to/.venv/bin/python /path/to/set_tts.py $ARGUMENTS
```

Restart Claude Code after creating either file for the commands to appear in autocomplete.

## Configuration (`config.json`)

Voice, speed, model, and character limit are stored in `config.json` at the repo root. The daemon and hook read this file on every synthesis — no restart needed when you change it.

```json
{
  "model": "KittenML/kitten-tts-mini-0.8",
  "voice": "Hugo",
  "speed": 1.3,
  "char_limit": 600
}
```

## Experimenting with parameters

Use `sample.py` to quickly try different voices, speeds, and models without going through the daemon:

```bash
# defaults: Hugo voice, 1.3x speed, mini model
.venv/bin/python sample.py

# different voice and speed
.venv/bin/python sample.py --voice Rosie --speed 0.9

# custom text
.venv/bin/python sample.py --voice Jasper --speed 1.2 --text "Testing one two three"

# try a smaller model (must be downloaded first via test_tts.py)
.venv/bin/python sample.py --model KittenML/kitten-tts-nano-0.8-int8 --voice Bruno
```

Once you find settings you like, save them with `/tts-set` or edit `config.json` directly.

## Basic API usage

```python
from kittentts import KittenTTS
import soundfile as sf

model = KittenTTS("KittenML/kitten-tts-mini-0.8")

audio = model.generate("Hello, world.", voice="Luna", speed=1.0)
sf.write("output.wav", audio, 24000)

# Or write directly to file
model.generate_to_file("Hello, world.", "output.wav", voice="Jasper", speed=1.0)
```

## Available voices

`Bella`, `Jasper`, `Luna`, `Bruno`, `Rosie`, `Hugo`, `Kiki`, `Leo`

## Available models

| Model | Params | Size | HF repo |
|-------|--------|------|---------|
| mini | 80M | ~80 MB | `KittenML/kitten-tts-mini-0.8` |
| micro | 40M | ~41 MB | `KittenML/kitten-tts-micro-0.8` |
| nano fp32 | 15M | ~56 MB | `KittenML/kitten-tts-nano-0.8-fp32` |
| nano int8 | 15M | ~25 MB | `KittenML/kitten-tts-nano-0.8-int8` |

To switch models, update `config.json` and run `test_tts.py` once to download the new weights if needed.

## Notes

- Model weights are cached at `~/.cache/huggingface/hub`. After first download the daemon never contacts the network.
- The `kittentts` package on PyPI (0.1.x) has a different API than 0.8.x. This project pins to the 0.8.1 GitHub release wheel.
- Daemon logs: `/tmp/tts-daemon.log`. Hook logs: `/tmp/tts-speak.log`.
