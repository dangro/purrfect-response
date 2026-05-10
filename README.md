# purrfect-response

A Claude Code integration that reads every assistant response aloud using [KittenTTS](https://github.com/KittenML/KittenTTS), a lightweight, locally-run TTS model.

> **Authorship:** this repo was built with Claude Code. I claim no pure authorship of the code here. Given enough time I could have built most of this myself, but the honest answer is it would have taken me years, if I ever finished at all. Claude Code made it an afternoon.

> **Fair warning:** this is a novelty. It is genuinely fun for the first few sessions and then you will probably find it annoying. It works best when you are working on something exploratory and want to absorb responses without staring at the screen. It is not suitable for every environment: open offices, calls, or anywhere you can't have audio playing.

## How it works

A persistent background daemon keeps the ONNX model loaded in memory. A Claude Code **Stop hook** fires after every response, strips and normalizes the text, and streams sentences to the daemon one at a time. The daemon plays each sentence as soon as it is synthesized while generating the next, so audio starts within a second or two of Claude finishing.

Two **slash commands** let you interrupt playback or adjust parameters on the fly.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)
- `espeak-ng` system library (required by phonemizer)
- Claude Code

### Install espeak-ng

**Ubuntu/Debian / WSL2:**
```bash
sudo apt install espeak-ng
```

**macOS:**
```bash
brew install espeak-ng
```

**Windows (native):**
Download and install from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases).

Audio playback on WSL2 uses Windows audio via PowerShell. No extra setup is needed as long as you are on Windows 11.

## Installation

There are two ways to set this up.

### Option A: Let Claude do it

Clone the repo, then open Claude Code in the project directory and paste this prompt:

> Read the README and set up purrfect-response from scratch. Install the hook in my global Claude Code settings, create the slash commands, start the daemon, and confirm audio is working.

Claude will read the README and handle everything: hook configuration, slash command files, and a test run.

### Option B: Manual setup

**1. Install dependencies:**

```bash
git clone <repo-url>
cd purrfect-response
uv sync
```

`uv sync` installs all dependencies including the KittenTTS 0.8.1 wheel from the GitHub release. On first run, model weights (~80 MB for mini) are downloaded from Hugging Face and cached locally. After that, no network calls are made. The daemon loads exclusively from cache.

**2. Download the model:**

```bash
uv run python test_tts.py
```

This triggers the first download and generates sample `.wav` files to confirm synthesis is working.

**3. Start the daemon:**

```bash
nohup .venv/bin/python tts_daemon.py > /tmp/tts-daemon.log 2>&1 &
```

**4. Wire up the Stop hook** in `~/.claude/settings.json` (merge with any existing content):

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

Update both paths to match your install location. Restart Claude Code to reload.

**5. Install slash commands** by creating these two files (update paths):

`~/.claude/commands/stop-tts.md`:
```markdown
Stop TTS playback immediately, clearing any queued audio.

!  /path/to/.venv/bin/python /path/to/stop_tts.py
```

`~/.claude/commands/tts-set.md`:
```markdown
Update TTS parameters. Changes take effect on the next spoken sentence (no daemon restart needed).

Usage: /tts-set --voice Luna --speed 1.1 --char-limit 800

Available voices: Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo

! /path/to/.venv/bin/python /path/to/set_tts.py $ARGUMENTS
```

Restart Claude Code for the slash commands to appear in autocomplete.

## Managing the daemon

Stop:
```bash
kill $(cat /tmp/purrfect-response.pid)
```

Check if running:
```bash
ls /tmp/purrfect-response.sock && echo "running" || echo "not running"
```

Logs: `/tmp/tts-daemon.log`

The daemon auto-starts if the hook fires and the socket is missing.

## Hook behaviour (`speak.py`)

The Stop hook processes text through several stages:

1. **Markdown stripping** — fenced code blocks become "code block.", inline code backticks are stripped (content kept), headers/bold/links are unwrapped, list items become period-terminated sentences.
2. **TTS normalization** — arrows become spoken words, URLs become "link", `snake_case` and `camelCase` are spaced out, common abbreviations (`e.g.`, `i.e.`, `etc.`) are expanded, known acronyms (`API`, `CLI`, `TTS`, etc.) have their letters spaced for correct pronunciation, filenames like `config.json` are read as "config dot json".
3. **Sentence splitting** — splits on sentence-ending punctuation and em-dashes.
4. **Character cap** — only the first N characters worth of sentences are sent (configurable in `config.json`, default 600), so long responses start playing quickly.

When a turn ends with a tool call rather than a text response, `last_assistant_message` is empty. The hook falls back to reading the transcript JSONL directly.

To skip TTS for a specific response, include `#notts` anywhere in your message.

## Configuration (`config.json`)

Voice, speed, model, and character limit live in `config.json`. The daemon and hook read this on every synthesis, so changes take effect immediately without a restart.

```json
{
  "model": "KittenML/kitten-tts-mini-0.8",
  "voice": "Hugo",
  "speed": 1.3,
  "char_limit": 600
}
```

Update via slash command:
```
/tts-set --voice Luna --speed 1.1
/tts-set --char-limit 800
```

Or directly:
```bash
.venv/bin/python set_tts.py --voice Rosie --speed 0.9
```

## Experimenting with voices and speed

Use `sample.py` to audition voices and speeds without going through the daemon:

```bash
.venv/bin/python sample.py --voice Rosie --speed 0.9
.venv/bin/python sample.py --voice Jasper --speed 1.2 --text "Testing one two three"
.venv/bin/python sample.py --model KittenML/kitten-tts-nano-0.8-int8 --voice Bruno
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

To switch models, update `config.json` and run `test_tts.py` once to download the weights if not already cached.

## Basic API usage

```python
from kittentts import KittenTTS
import soundfile as sf

model = KittenTTS("KittenML/kitten-tts-mini-0.8")

audio = model.generate("Hello, world.", voice="Luna", speed=1.0)
sf.write("output.wav", audio, 24000)
```

## Notes

- Model weights are cached at `~/.cache/huggingface/hub`. After first download the daemon never contacts the network.
- The `kittentts` package on PyPI (0.1.x) has a different API than 0.8.x. This project pins to the 0.8.1 GitHub release wheel.
- Daemon logs: `/tmp/tts-daemon.log`. Hook logs: `/tmp/tts-speak.log`.
