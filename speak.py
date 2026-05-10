#!/usr/bin/env python3
"""Stop hook script — forwards last assistant message to the TTS daemon."""
import ast
import json
import os
import re
import socket
import subprocess
import sys
import time

SOCKET_PATH = "/tmp/purrfect-response.sock"
DAEMON = os.path.join(os.path.dirname(__file__), "tts_daemon.py")
PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def read_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"char_limit": 600}


def strip_markdown(text):
    text = re.sub(r"```[\s\S]*?```", " code block. ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Convert list items into sentences before collapsing whitespace.
    # Each item gets a trailing period so split_sentences can break on it.
    def list_to_sentence(m):
        content = m.group(1).strip()
        if content and content[-1] not in ".!?,;:":
            content += "."
        return content + "\n"

    text = re.sub(r"^[ \t]*[-*+]\s+(.+)$", list_to_sentence, text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*\d+\.\s+(.+)$", list_to_sentence, text, flags=re.MULTILINE)

    text = re.sub(r"\s+", " ", text)
    return text.strip()


ABBREVIATIONS = {
    r"\be\.g\.": "for example",
    r"\bi\.e\.": "that is",
    r"\betc\.": "and so on",
    r"\bvs\.": "versus",
    r"\bapprox\.": "approximately",
    r"\bmin\.": "minutes",
    r"\bmax\.": "maximum",
    r"\bno\.": "number",
}

ACRONYMS = {
    "API", "TTS", "URL", "HTTP", "HTTPS", "SQL", "JSON", "CLI",
    "GPU", "CPU", "RAM", "SDK", "IDE", "LLM", "AI", "ML", "UI",
    "UX", "OS", "CI", "CD", "PR", "WSL",
}


def normalize_for_tts(text):
    # Arrows and symbols
    text = re.sub(r"\s*→\s*", " becomes ", text)
    text = re.sub(r"\s*=>\s*", " becomes ", text)
    text = re.sub(r"\s*->\s*", " becomes ", text)
    text = re.sub(r"\s*<-\s*", " from ", text)
    text = re.sub(r"~", "approximately ", text)

    # URLs — replace with "link"
    text = re.sub(r"https?://\S+", "link", text)

    # File paths — keep just the last component
    text = re.sub(r"(?:[\w./~-]+/)+(\w[\w.-]*)", r"\1", text)

    # snake_case and camelCase → spaced words
    text = re.sub(r"([a-z])_([a-z])", r"\1 \2", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # Abbreviations
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Acronyms — space out letters so TTS reads them individually
    def space_acronym(m):
        word = m.group(0)
        if word in ACRONYMS:
            return " ".join(word)
        return word

    text = re.sub(r"\b[A-Z]{2,}\b", space_acronym, text)

    # Numbers with commas → no commas
    text = re.sub(r"(\d),(\d{3})", r"\1\2", text)

    # Filenames: word.ext → "word dot ext"
    text = re.sub(
        r"\b(\w+)\.(py|json|md|txt|wav|toml|sh|js|ts|yaml|yml|log|env|cfg|ini|html|css)\b",
        r"\1 dot \2",
        text,
    )

    return text


def split_sentences(text):
    """Split text into sentences at natural spoken boundaries."""
    # Split on sentence-ending punctuation followed by a space.
    # No capital-letter requirement — list items may start lowercase.
    parts = re.split(r"(?<=[.!?])\s+", text)
    sentences = []
    for part in parts:
        # Also split on em-dashes used as sentence breaks
        sub = re.split(r"\s+—\s+", part.strip())
        sentences.extend(s.strip() for s in sub if s.strip())
    return sentences


def ensure_daemon():
    for _ in range(20):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCKET_PATH)
            s.close()
            return True
        except (FileNotFoundError, ConnectionRefusedError):
            pass
        # Start daemon on first failure
        if _ == 0:
            subprocess.Popen(
                [PYTHON, DAEMON],
                stdout=subprocess.DEVNULL,
                stderr=open("/tmp/tts-daemon.log", "a"),
            )
        time.sleep(0.3)
    return False


def last_user_text_from_transcript(path):
    """Return the last user message text from the transcript JSONL."""
    try:
        last = ""
        with open(path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") not in ("human", "user"):
                    continue
                msg = entry.get("message", {})
                if isinstance(msg, str):
                    try:
                        msg = ast.literal_eval(msg)
                    except Exception:
                        continue
                content = msg.get("content", [])
                if isinstance(content, str):
                    if content:
                        last = content
                else:
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                last = text
        return last
    except Exception:
        return ""


def last_text_from_transcript(path):
    """Read the transcript JSONL and return the last assistant text block."""
    try:
        last = ""
        with open(path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                msg = entry.get("message", {})
                if isinstance(msg, str):
                    try:
                        msg = ast.literal_eval(msg)
                    except Exception:
                        continue
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        last = block.get("text", "")
        return last
    except Exception:
        return ""


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        log("speak.py: empty stdin")
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"speak.py: JSON parse error: {e}")
        return

    raw_msg = data.get("last_assistant_message", "")

    # When a turn ends with a tool call rather than text, last_assistant_message
    # is empty. Fall back to the last text block in the transcript file.
    if not raw_msg and data.get("transcript_path"):
        raw_msg = last_text_from_transcript(data["transcript_path"])

    if data.get("transcript_path"):
        user_text = last_user_text_from_transcript(data["transcript_path"])
        if "#notts" in user_text:
            log("speak.py: #notts detected, skipping TTS")
            return

    log(f"speak.py: last_assistant_message length={len(raw_msg)} preview={repr(raw_msg[:80])}")

    text = strip_markdown(raw_msg)
    if not text:
        log("speak.py: text empty after strip_markdown")
        return

    text = normalize_for_tts(text)
    sentences = split_sentences(text)
    char_limit = read_config().get("char_limit", 600)
    kept, total = [], 0
    for s in sentences:
        if total + len(s) > char_limit:
            break
        kept.append(s)
        total += len(s)
    if not kept:
        kept = [text[:300] + "."]

    log(f"speak.py: {len(kept)} chunk(s), total {total} chars")

    if not ensure_daemon():
        log("speak.py: daemon unavailable")
        return

    for sentence in kept:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCKET_PATH)
            s.sendall(sentence.encode("utf-8"))
            s.close()
        except Exception as e:
            log(f"speak.py: send error: {e}")
            break
    log("speak.py: all chunks sent")


if __name__ == "__main__":
    main()
