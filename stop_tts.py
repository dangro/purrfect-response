#!/usr/bin/env python3
"""Interrupt TTS playback — clears the queue and stops the current audio."""
import socket
import sys

SOCKET_PATH = "/tmp/claude-tts.sock"

try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCKET_PATH)
    s.sendall(b"STOP")
    s.close()
except FileNotFoundError:
    print("TTS daemon not running.", file=sys.stderr)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
