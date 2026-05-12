#!/usr/bin/env python3
"""Persistent TTS daemon — pipeline (generate + play) with stop support."""
import json
import os
import queue
import socket
import subprocess
import sys
import tempfile
import threading

SOCKET_PATH = "/tmp/purrfect-response.sock"
PID_FILE = "/tmp/purrfect-response.pid"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def read_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"voice": "Hugo", "speed": 1.3}


def get_windows_temp():
    win = subprocess.check_output(["cmd.exe", "/c", "echo %TEMP%"]).decode().strip()
    return subprocess.check_output(["wslpath", win]).decode().strip()


def load_model_from_cache(repo_id=None):
    """Load model directly from HuggingFace local cache — no network calls."""
    from huggingface_hub import try_to_load_from_cache
    from kittentts.onnx_model import KittenTTS_1_Onnx

    config_path = try_to_load_from_cache(repo_id, "config.json")
    if config_path is None:
        raise FileNotFoundError(
            f"Model {repo_id} not in cache. Run test_tts.py once to download it."
        )
    with open(config_path) as f:
        config = json.load(f)
    return KittenTTS_1_Onnx(
        model_path=try_to_load_from_cache(repo_id, config["model_file"]),
        voices_path=try_to_load_from_cache(repo_id, config["voices"]),
        speed_priors=config.get("speed_priors", {}),
        voice_aliases=config.get("voice_aliases", {}),
    )


class Daemon:
    def __init__(self, model, wsl_temp):
        self.model = model
        self.wsl_temp = wsl_temp
        # gen_q: raw text chunks waiting to be synthesised
        # play_q: (text, audio) ready for playback; maxsize limits lookahead
        self.gen_q = queue.Queue()
        self.play_q = queue.Queue(maxsize=2)
        self._current_proc = None
        self._proc_lock = threading.Lock()
        self._stop_gen = 0   # generation counter — chunks with stale id are discarded
        self._stop_lock = threading.Lock()

    # ------------------------------------------------------------------ stop

    def stop(self):
        with self._stop_lock:
            self._stop_gen += 1
            gen = self._stop_gen

        # drain queues so blocked threads wake up
        for q in (self.gen_q, self.play_q):
            while True:
                try:
                    q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break

        # kill current powershell playback
        with self._proc_lock:
            if self._current_proc and self._current_proc.poll() is None:
                self._current_proc.terminate()

    # ---------------------------------------------------------------- threads

    def generator_thread(self):
        while True:
            item = self.gen_q.get()
            text, gen_id = item
            with self._stop_lock:
                current = self._stop_gen
            if gen_id != current:
                self.gen_q.task_done()
                continue
            try:
                cfg = read_config()
                audio = self.model.generate(text, voice=cfg.get("voice", "Hugo"), speed=cfg.get("speed", 1.3))
            except Exception as e:
                print(f"Generate error: {e}", file=sys.stderr, flush=True)
                self.gen_q.task_done()
                continue
            with self._stop_lock:
                current = self._stop_gen
            if gen_id == current:
                self.play_q.put((audio, gen_id))
            self.gen_q.task_done()

    def player_thread(self):
        import soundfile as sf
        while True:
            item = self.play_q.get()
            audio, gen_id = item
            with self._stop_lock:
                current = self._stop_gen
            if gen_id != current:
                self.play_q.task_done()
                continue
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False, dir=self.wsl_temp
                ) as f:
                    tmp = f.name
                sf.write(tmp, audio, 24000)
                win = subprocess.check_output(["wslpath", "-w", tmp]).decode().strip()
                proc = subprocess.Popen(
                    ["powershell.exe", "-c",
                     f'(New-Object Media.SoundPlayer "{win}").PlaySync()'],
                )
                with self._proc_lock:
                    self._current_proc = proc
                proc.wait()
            except Exception as e:
                print(f"Play error: {e}", file=sys.stderr, flush=True)
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
                self.play_q.task_done()

    # ------------------------------------------------------------------ enqueue

    def enqueue(self, text):
        with self._stop_lock:
            gen_id = self._stop_gen
        self.gen_q.put((text, gen_id))


def main():
    print("Loading TTS model...", file=sys.stderr, flush=True)
    cfg = read_config()
    repo_id = cfg.get("model", "KittenML/kitten-tts-nano-0.8-int8")
    print(f"Loading model: {repo_id}", file=sys.stderr, flush=True)
    model = load_model_from_cache(repo_id)
    wsl_temp = get_windows_temp()
    print("Model ready. Listening on socket.", file=sys.stderr, flush=True)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    daemon = Daemon(model, wsl_temp)

    threading.Thread(target=daemon.generator_thread, daemon=True).start()
    threading.Thread(target=daemon.player_thread, daemon=True).start()

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(16)
    os.chmod(SOCKET_PATH, 0o666)

    while True:
        conn, _ = server.accept()
        try:
            chunks = []
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            text = b"".join(chunks).decode("utf-8").strip()
            if text == "STOP":
                daemon.stop()
            elif text:
                daemon.enqueue(text)
        except Exception as e:
            print(f"Accept error: {e}", file=sys.stderr, flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
