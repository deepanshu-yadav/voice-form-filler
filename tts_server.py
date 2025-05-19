import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io
import numpy as np
import soundfile as sf
import uvicorn
from pydantic import BaseModel
from kokoro_onnx import Kokoro
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kokoro TTS API Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Kokoro model
@app.on_event("startup")
async def startup_event():
    app.state.kokoro = Kokoro(
        os.path.join("models", "kokoro-v1.0.onnx"), 
        os.path.join("models", "voices-v1.0.bin")
    )
    logger.info("Kokoro TTS model loaded successfully")

# Model for text input
class TextInput(BaseModel):
    text: str
    voice: str = "af_nicole"
    speed: float = 1.0
    language: str = "en-us"

# API routes
@app.get("/")
async def root():
    return {
        "message": "Kokoro TTS API Server",
        "endpoints": {
            "POST /api/tts": "Generate complete audio file from text",
            "WebSocket /ws/stream": "Stream audio chunks as they're generated",
            "GET /api/voices": "List available voices"
        }
    }

@app.get("/api/voices")
async def list_voices():
    return {
        "voices": [
            {"id": "af_nicole", "name": "Nicole", "region": "African"},
            {"id": "us_tom", "name": "Tom", "region": "US"},
            {"id": "us_mark", "name": "Mark", "region": "US"},
            {"id": "us_nancy", "name": "Nancy", "region": "US"},
            {"id": "gb_emma", "name": "Emma", "region": "UK"},
            {"id": "in_priya", "name": "Priya", "region": "Indian"}
        ]
    }

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        request = TextInput.parse_raw(data)
        logger.info(f"Received streaming TTS request: {request.text[:30]}...")
        
        # Create stream with Kokoro
        stream = app.state.kokoro.create_stream(
            request.text,
            voice=request.voice,
            speed=request.speed,
            lang=request.language,
        )
        
        # Stream each audio chunk as it's generated
        chunk_count = 0
        async for samples, sample_rate in stream:
            chunk_count += 1
            logger.info(f"Sending audio chunk {chunk_count}...")
            
            # Convert numpy array to WAV bytes
            wav_bytes = io.BytesIO()
            sf.write(wav_bytes, samples, sample_rate, format='WAV')
            wav_bytes.seek(0)
            
            # Send the WAV bytes over the websocket
            await websocket.send_bytes(wav_bytes.read())
            
        logger.info(f"Audio streaming completed with {chunk_count} chunks")
        
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error processing streaming TTS request: {str(e)}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
        except:
            pass

# REST API endpoint for single audio file
@app.post("/api/tts")
async def tts(request: TextInput):
    try:
        logger.info(f"Received TTS request: {request.text[:30]}...")
        
        # Create stream with Kokoro
        stream = app.state.kokoro.create_stream(
            request.text,
            voice=request.voice,
            speed=request.speed,
            lang=request.language,
        )
        
        # Collect all audio samples
        all_samples = []
        sample_rate = None
        
        async for samples, sr in stream:
            all_samples.append(samples)
            sample_rate = sr
        
        # Concatenate samples if multiple chunks were generated
        if all_samples:
            combined_samples = np.concatenate(all_samples) if len(all_samples) > 1 else all_samples[0]
            
            # Convert to WAV bytes
            wav_bytes = io.BytesIO()
            sf.write(wav_bytes, combined_samples, sample_rate, format='WAV')
            wav_bytes.seek(0)
            
            logger.info(f"Audio generation completed, total length: {len(combined_samples) / sample_rate:.2f} seconds")
            
            return StreamingResponse(
                wav_bytes, 
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=tts-audio.wav"}
            )
        else:
            return {"error": "No audio was generated"}
            
    except Exception as e:
        logger.error(f"Error processing TTS request: {str(e)}")
        return {"error": str(e)}

# Run the server
if __name__ == "__main__":
    print("Starting Kokoro TTS API Server...")
    print("Make sure you have the following dependencies installed:")
    print("  - fastapi, uvicorn, numpy, soundfile, and kokoro_onnx")
    print("  - Models directory with kokoro-v1.0.onnx and voices-v1.0.bin files")
    print("\nAPI is accessible at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)