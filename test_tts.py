import json, os
from kittentts import KittenTTS
import soundfile as sf

_config = json.load(open(os.path.join(os.path.dirname(__file__), "config.json")))
model = KittenTTS(_config.get("model", "KittenML/kitten-tts-nano-0.8-int8"))

print(f"Available voices: {model.available_voices}")

# Basic generation (docs example)
audio = model.generate("This high-quality TTS model runs without a GPU.", voice="Jasper")
sf.write("output.wav", audio, 24000)
print("Saved output.wav")

# Speed variants
for speed in [0.8, 1.0, 1.2]:
    audio = model.generate("Testing speech speed.", voice="Luna", speed=speed)
    sf.write(f"output_speed_{speed}.wav", audio, 24000)
    print(f"Saved output_speed_{speed}.wav")

# All voices
for voice in model.available_voices:
    model.generate_to_file("Hello from Kitten TTS.", f"output_{voice}.wav", voice=voice)
    print(f"Saved output_{voice}.wav")
