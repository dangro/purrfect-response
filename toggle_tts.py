#!/usr/bin/env python3
"""Toggle TTS on or off. Persisted in config.json."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def main():
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    except Exception:
        config = {}

    config["enabled"] = not config.get("enabled", True)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    state = "on" if config["enabled"] else "off"
    print(f"TTS {state}")


if __name__ == "__main__":
    main()
