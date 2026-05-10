#!/usr/bin/env python3
"""Quick TTS sample — generate and play with custom parameters."""
import argparse
import json
import os
import subprocess
import tempfile

VOICES = ["Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo"]
DEFAULT_TEXT = "Hello! This is a sample of the text-to-speech system."


def load_model(repo_id):
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


def get_windows_temp():
    win = subprocess.check_output(["cmd.exe", "/c", "echo %TEMP%"]).decode().strip()
    return subprocess.check_output(["wslpath", win]).decode().strip()


def play(audio, wsl_temp):
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=wsl_temp) as f:
        tmp = f.name
    try:
        sf.write(tmp, audio, 24000)
        win = subprocess.check_output(["wslpath", "-w", tmp]).decode().strip()
        subprocess.run(
            ["powershell.exe", "-c", f'(New-Object Media.SoundPlayer "{win}").PlaySync()'],
            check=True,
        )
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser = argparse.ArgumentParser(description="Generate and play a TTS sample.")
    parser.add_argument("--voice", default="Luna", choices=VOICES)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument(
        "--model",
        default="KittenML/kitten-tts-mini-0.8",
        help="HuggingFace repo ID",
    )
    parser.add_argument("--text", default=DEFAULT_TEXT)
    args = parser.parse_args()

    print(f"voice={args.voice}  speed={args.speed}  model={args.model}")
    print(f"text: {args.text}")
    print("Loading model...", end=" ", flush=True)
    model = load_model(args.model)
    print("done. Generating...", end=" ", flush=True)
    audio = model.generate(args.text, voice=args.voice, speed=args.speed)
    print("done. Playing...")
    play(audio, get_windows_temp())


if __name__ == "__main__":
    main()
