# purrfect-response TODO

## Pending


## Done

- [x] Basic KittenTTS integration with local ONNX inference
- [x] Persistent daemon to keep model in memory (low latency)
- [x] Cache-only model loading (no network calls after first download)
- [x] Sentence chunking + pipeline (generate N+1 while playing N)
- [x] Stop/interrupt command via socket (`stop_tts.py`)
- [x] Claude Code Stop hook wired to global settings
- [x] `/stop-tts` slash command to interrupt TTS (keybindings can't run arbitrary scripts)
- [x] TTS configuration via `config.json` and `/tts-set` slash command (voice, speed, model, char limit)
- [x] `#notts` to skip TTS for a specific response
- [x] `/tts-toggle` slash command to enable or disable TTS globally
