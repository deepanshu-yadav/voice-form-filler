import asyncio

import sounddevice as sd

from kokoro_onnx import Kokoro
import os

text = """
This is a test for the Kokoro speech synthesis model.
"""

async def main():
    kokoro = Kokoro(os.path.join("models", "kokoro-v1.0.onnx"), os.path.join("models", "voices-v1.0.bin"))

    stream = kokoro.create_stream(
        text,
        voice="af_nicole",
        speed=1.0,
        lang="en-us",
    )
    count = 0
    async for samples, sample_rate in stream:
        count += 1
        print(f"Playing audio stream ({count})...")
        sd.play(samples, sample_rate)
        sd.wait()

asyncio.run(main())
