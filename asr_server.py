#!/usr/bin/env python3
# Copyright 2025 Xiaomi Corp. (authors: Fangjun Kuang)
# Modified for WebSocket server with chunked audio and stop signal

import argparse
import asyncio
import json
import os
import io
import tempfile
from pathlib import Path
import websockets
import kaldi_native_fbank as knf
import librosa
import numpy as np
import onnxruntime as ort
import soundfile as sf
import torch
import time
from pydub import AudioSegment  # For handling webm chunks

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--encoder", type=str, required=True, help="Path to encoder.onnx"
    )
    parser.add_argument(
        "--decoder", type=str, required=True, help="Path to decoder.onnx"
    )
    parser.add_argument("--joiner", type=str, required=True, help="Path to joiner.onnx")
    parser.add_argument("--tokens", type=str, required=True, help="Path to tokens.txt")
    parser.add_argument("--port", type=int, default=8001, help="WebSocket server port")
    return parser.parse_args()

def create_fbank():
    opts = knf.FbankOptions()
    opts.frame_opts.dither = 0
    opts.frame_opts.remove_dc_offset = False
    opts.frame_opts.window_type = "hann"
    opts.mel_opts.low_freq = 0
    opts.mel_opts.num_bins = 128
    opts.mel_opts.is_librosa = True
    fbank = knf.OnlineFbank(opts)
    return fbank

def compute_features(audio, fbank):
    assert len(audio.shape) == 1, audio.shape
    fbank.accept_waveform(16000, audio)
    ans = []
    processed = 0
    while processed < fbank.num_frames_ready:
        ans.append(np.array(fbank.get_frame(processed)))
        processed += 1
    ans = np.stack(ans)
    return ans

def display(sess, model):
    print(f"=========={model} Input==========")
    for i in sess.get_inputs():
        print(i)
    print(f"=========={model} Output==========")
    for i in sess.get_outputs():
        print(i)

class OnnxModel:
    def __init__(self, encoder: str, decoder: str, joiner: str):
        self.init_encoder(encoder)
        display(self.encoder, "encoder")
        self.init_decoder(decoder)
        display(self.decoder, "decoder")
        self.init_joiner(joiner)
        display(self.joiner, "joiner")

    def init_encoder(self, encoder):
        session_opts = ort.SessionOptions()
        session_opts.inter_op_num_threads = 1
        session_opts.intra_op_num_threads = 1
        self.encoder = ort.InferenceSession(
            encoder,
            sess_options=session_opts,
            providers=["CPUExecutionProvider"],
        )
        meta = self.encoder.get_modelmeta().custom_metadata_map
        self.normalize_type = meta["normalize_type"]
        print(meta)
        self.pred_rnn_layers = int(meta["pred_rnn_layers"])
        self.pred_hidden = int(meta["pred_hidden"])

    def init_decoder(self, decoder):
        session_opts = ort.SessionOptions()
        session_opts.inter_op_num_threads = 1
        session_opts.intra_op_num_threads = 1
        self.decoder = ort.InferenceSession(
            decoder,
            sess_options=session_opts,
            providers=["CPUExecutionProvider"],
        )

    def init_joiner(self, joiner):
        session_opts = ort.SessionOptions()
        session_opts.inter_op_num_threads = 1
        session_opts.intra_op_num_threads = 1
        self.joiner = ort.InferenceSession(
            joiner,
            sess_options=session_opts,
            providers=["CPUExecutionProvider"],
        )

    def get_decoder_state(self):
        batch_size = 1
        state0 = torch.zeros(self.pred_rnn_layers, batch_size, self.pred_hidden).numpy()
        state1 = torch.zeros(self.pred_rnn_layers, batch_size, self.pred_hidden).numpy()
        return state0, state1

    def run_encoder(self, x: np.ndarray):
        x = torch.from_numpy(x)
        x = x.t().unsqueeze(0)
        x_lens = torch.tensor([x.shape[-1]], dtype=torch.int64)
        (encoder_out, out_len) = self.encoder.run(
            [self.encoder.get_outputs()[0].name, self.encoder.get_outputs()[1].name],
            {
                self.encoder.get_inputs()[0].name: x.numpy(),
                self.encoder.get_inputs()[1].name: x_lens.numpy(),
            },
        )
        return encoder_out

    def run_decoder(self, token: int, state0: np.ndarray, state1: np.ndarray):
        target = torch.tensor([[token]], dtype=torch.int32).numpy()
        target_len = torch.tensor([1], dtype=torch.int32).numpy()
        (decoder_out, decoder_out_length, state0_next, state1_next,) = self.decoder.run(
            [
                self.decoder.get_outputs()[0].name,
                self.decoder.get_outputs()[1].name,
                self.decoder.get_outputs()[2].name,
                self.decoder.get_outputs()[3].name,
            ],
            {
                self.decoder.get_inputs()[0].name: target,
                self.decoder.get_inputs()[1].name: target_len,
                self.decoder.get_inputs()[2].name: state0,
                self.decoder.get_inputs()[3].name: state1,
            },
        )
        return decoder_out, state0_next, state1_next

    def run_joiner(self, encoder_out: np.ndarray, decoder_out: np.ndarray):
        logit = self.joiner.run(
            [self.joiner.get_outputs()[0].name],
            {
                self.joiner.get_inputs()[0].name: encoder_out,
                self.joiner.get_inputs()[1].name: decoder_out,
            },
        )[0]
        return logit

async def process_audio(websocket, model, id2token):
    audio_chunks = []
    tmp_file = None
    try:
        async for message in websocket:
            try:
                # Check if the message is a stop signal
                if isinstance(message, str):
                    data = json.loads(message)
                    if data.get("type") == "stop":
                        print("Received stop signal")
                        if not audio_chunks:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "No audio chunks received"
                            }))
                            continue
                        # Combine chunks into a single audio file
                        audio_data = b''.join(audio_chunks)
                        # Convert webm chunks to WAV
                        try:
                            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
                            tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                            audio.export(tmp_file.name, format="wav")
                            wav_path = tmp_file.name
                        except Exception as e:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": f"Failed to convert audio chunks to WAV: {str(e)}"
                            }))
                            audio_chunks = []
                            continue

                        # Process the WAV file with ASR
                        start = time.time()
                        fbank = create_fbank()
                        audio, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
                        audio = audio[:, 0]  # Use first channel
                        if sample_rate != 16000:
                            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
                            sample_rate = 16000

                        tail_padding = np.zeros(sample_rate * 2)
                        audio = np.concatenate([audio, tail_padding])

                        blank = len(id2token) - 1
                        ans = [blank]
                        state0, state1 = model.get_decoder_state()
                        decoder_out, state0_next, state1_next = model.run_decoder(ans[-1], state0, state1)

                        features = compute_features(audio, fbank)
                        if model.normalize_type != "":
                            assert model.normalize_type == "per_feature", model.normalize_type
                            features = torch.from_numpy(features)
                            mean = features.mean(dim=1, keepdims=True)
                            stddev = features.std(dim=1, keepdims=True) + 1e-5
                            features = (features - mean) / stddev
                            features = features.numpy()

                        encoder_out = model.run_encoder(features)
                        for t in range(encoder_out.shape[2]):
                            encoder_out_t = encoder_out[:, :, t : t + 1]
                            logits = model.run_joiner(encoder_out_t, decoder_out)
                            logits = torch.from_numpy(logits)
                            logits = logits.squeeze()
                            idx = torch.argmax(logits, dim=-1).item()
                            if idx != blank:
                                ans.append(idx)
                                state0 = state0_next
                                state1 = state1_next
                                decoder_out, state0_next, state1_next = model.run_decoder(
                                    ans[-1], state0, state1
                                )

                        end = time.time()
                        elapsed_seconds = end - start
                        audio_duration = audio.shape[0] / 16000
                        real_time_factor = elapsed_seconds / audio_duration

                        ans = ans[1:]  # Remove the first blank
                        tokens = [id2token[i] for i in ans]
                        underline = "▁"
                        text = "".join(tokens).replace(underline, " ").strip()

                        # Send transcription back to client
                        await websocket.send(json.dumps({
                            "type": "fullSentence",
                            "text": text,
                            "rtf": real_time_factor
                        }))
                        audio_chunks = []  # Clear chunks after processing
                        continue

                # Treat binary data as an audio chunk
                if isinstance(message, bytes):
                    print(f"Received audio chunk, size: {len(message)} bytes")
                    audio_chunks.append(message)
            except json.JSONDecodeError:
                print("Received non-JSON message, treating as audio chunk")
                audio_chunks.append(message)
            except Exception as e:
                print(f"Error processing message: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed while receiving data")
    finally:
        if tmp_file is not None and os.path.exists(tmp_file.name):
            try:
                os.unlink(tmp_file.name)
            except Exception as e:
                print(f"Error removing temporary file: {e}")
        print("Connection closed")

async def main():
    args = get_args()
    assert Path(args.encoder).is_file(), args.encoder
    assert Path(args.decoder).is_file(), args.decoder
    assert Path(args.joiner).is_file(), args.joiner
    assert Path(args.tokens).is_file(), args.tokens

    model = OnnxModel(args.encoder, args.decoder, args.joiner)
    id2token = dict()
    with open(args.tokens, encoding="utf-8") as f:
        for line in f:
            t, idx = line.split()
            id2token[int(idx)] = t

    async def handler(websocket):
        try:
            await process_audio(websocket, model, id2token)
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected")
        except Exception as e:
            print(f"Error in handler: {e}")

    print(f"Starting WebSocket server on ws://localhost:{args.port}")
    try:
        async with websockets.serve(
            handler,
            "localhost",
            args.port,
            ping_interval=20,
            ping_timeout=60
        ):
            print("Server started successfully")
            await asyncio.Future()  # Run forever
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    asyncio.run(main())