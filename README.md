We can use voice recognition to fill forms. 

https://github.com/user-attachments/assets/be8c74b8-681f-4242-96b2-65a0f696fd38



![Form](./images/form.png)

# Installation 
## Setting Up Your Environment

A simple guide to create an Anaconda environment and install required packages.

### Create and Set Up Environment

```bash
# Create a new conda environment with Python 3.10
conda create -n myenv python=3.10

# Activate the environment
conda activate myenv

# Install packages from requirements.txt
pip install -r requirements.txt
```

### Basic Usage

```bash
# Activate environment when needed
conda activate myenv

# Deactivate when finished
conda deactivate
```

# Downloading speech recognition models

```
mkdir models
cd models
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2
tar xvf sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2
rm sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2

wget https://dldata-public.s3.us-east-2.amazonaws.com/2086-149220-0033.wav
mv 2086-149220-0033.wav file.wav
cd ..
```
Finally execute the testing script as 

```
python ./test_model.py \
  --encoder ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/encoder.int8.onnx \
  --decoder ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/decoder.int8.onnx \
  --joiner ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/joiner.int8.onnx \
  --tokens ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/tokens.txt \
  --wav models/file.wav
```

# Test the TTS model

```
cd models
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ..
```

Now execute 
python test_speech_model.py

# Test the TTS server

`python tts_server.py`

and then click on `play_voice.html`

# Setup ffmpeg

    You can download an installer for your OS from the [ffmpeg Website](https://ffmpeg.org/download.html).  
    
    Or use a package manager:

    - **On Ubuntu or Debian**:
        ```bash
        sudo apt update && sudo apt install ffmpeg
        ```

    - **On Arch Linux**:
        ```bash
        sudo pacman -S ffmpeg
        ```

    - **On MacOS using Homebrew** ([https://brew.sh/](https://brew.sh/)):
        ```bash
        brew install ffmpeg
        ```

    - **On Windows using Winget** [official documentation](https://learn.microsoft.com/en-us/windows/package-manager/winget/) :
        ```bash
        winget install Gyan.FFmpeg
        ```
        
    - **On Windows using Chocolatey** ([https://chocolatey.org/](https://chocolatey.org/)):
        ```bash
        choco install ffmpeg
        ```

    - **On Windows using Scoop** ([https://scoop.sh/](https://scoop.sh/)):
        ```bash
        scoop install ffmpeg
        ```    

# Install Ollama 



Please Ollama installed (ollama.ai).
## Set Environment Variable
Enable CORS by setting OLLAMA_ORIGINS to allow requests from http://localhost:8080 (web server).
#### Windows (Command Prompt)
```
set OLLAMA_ORIGINS=http://localhost:8080
ollama serve
```

#### Windows (PowerShell)
```
$env:OLLAMA_ORIGINS="http://localhost:8080"
ollama serve
```

#### Linux/macOS
```
export OLLAMA_ORIGINS=http://localhost:8080
ollama serve
```

## Configure Model
Use the  granite3.1-dense:2b model for string correction.

#### Install Model:
```
ollama pull  granite3.1-dense:2b
```

#### Verify Model:
```
ollama list
```
Confirm  granite3.1-dense:2b is listed.


#### Test API:

Run the following curl command with proper JSON encoding:
```
  curl -X POST http://localhost:11434/api/generate -d "{\"model\":\"granite3.1-dense:2b\",\"prompt\":\"You are a string corrector. For the input string \\\"Dipanshu\\\", perform the action: \\\"Remove i and replace it with ee\\\". Return only the corrected string.\",\"stream\":false}"
```

#### Troubleshoot

Port Conflict:
Windows: netstat -aon | findstr :11434, then taskkill /PID <PID> /F.
Linux: lsof -i :11434, then kill -9 <PID>.

# Execution


First the recognition server
On Windows
```
python .\asr_server.py --encoder .\models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8\encoder.int8.onnx --decoder .\models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8\decoder.int8.onnx  --joiner .\models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8\joiner.int8.onnx --tokens .\models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8\tokens.txt --port 8001

```
On linux

```
python ./asr_server.py \
  --encoder ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/encoder.int8.onnx \
  --decoder ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/decoder.int8.onnx \
  --joiner ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/joiner.int8.onnx \
  --tokens ./models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/tokens.txt \
  --port 8001

```


Start the tts server (Text to Speech Server)

`python tts_server.py`


Now double click `voice-form.html`


# Credits
Thanks to repository which provided server implementation 

https://github.com/KoljaB/RealtimeSTT 

and 

https://github.com/k2-fsa/sherpa-onnx/tree/master

and 

https://github.com/thewh1teagle/kokoro-onnx

# Coming soon 
1. Support for languages other than english 
2. Voice output after filling the text field  -> Done
3. Interaction with only voice such as hey there is an extra r in my name after e or the ee in my name instead of i in my name. -> Done
4. Ability to execute this on tiny devices other than desktop. 
5. Streaming instead of sending .wav files to server. -> Done 



