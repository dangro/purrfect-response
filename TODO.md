# purrfect-response TODO

## Pending

- [ ] **TTS configuration** — add parameters to configure model (mini/micro/nano), voice, and speed. Should be adjustable without restarting the daemon (e.g. via a config file or socket command).

- [ ] **Disable TTS per-response or for N turns** — add a way to tell Claude to skip TTS for a specific response or suppress it for a given number of turns (e.g. "mute for 3 turns").

## Done

- [x] Basic KittenTTS integration with local ONNX inference
- [x] Persistent daemon to keep model in memory (low latency)
- [x] Cache-only model loading (no network calls after first download)
- [x] Sentence chunking + pipeline (generate N+1 while playing N)
- [x] Stop/interrupt command via socket (`stop_tts.py`)
- [x] Claude Code Stop hook wired to global settings
- [x] `/stop-tts` slash command to interrupt TTS (keybindings can't run arbitrary scripts)
