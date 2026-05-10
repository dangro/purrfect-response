#!/usr/bin/env python3
"""Update TTS config. Changes take effect on the next spoken sentence."""
import argparse
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
VOICES = ["Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo"]


def main():
    parser = argparse.ArgumentParser(description="Update TTS parameters.")
    parser.add_argument("--voice", choices=VOICES)
    parser.add_argument("--speed", type=float)
    parser.add_argument("--model")
    parser.add_argument("--char-limit", type=int, dest="char_limit")
    args = parser.parse_args()

    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    except Exception:
        config = {}

    if args.voice:
        config["voice"] = args.voice
    if args.speed is not None:
        config["speed"] = args.speed
    if args.model:
        config["model"] = args.model
    if args.char_limit is not None:
        config["char_limit"] = args.char_limit

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
