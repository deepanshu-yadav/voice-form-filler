// fill.js
// WebSocket and recording logic
let socket = null;
// Varriable for audio playback
let voiceSocket = null;
let audioQueue = [];
let isPlaying = false;
let currentSource = null;

let audioContext = null;
let displayDiv = document.getElementById('textDisplay');
let server_available = false;
let mic_available = false;
let fullSentences = [];
let mediaRecorder;
let audioChunks = [];
let isAskingCorrection = false
let stream;
let isRecording = false;
let activeFieldId = 'name'; // Default active field
const serverCheckInterval = 5000; // Check every 5 seconds
const formFields = ['name', 'address', 'email', 'phone'];
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
let reconnectTimeout = null;

// Set initial active field
document.getElementById(activeFieldId).classList.add('active-field');
document.getElementById(activeFieldId + 'Group').classList.add('recording');

function connectToServer() {
    // Clear any existing reconnect timeout
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }

    // Close existing connection if any
    if (socket) {
        try {
            socket.close();
        } catch (e) {
            console.error("Error closing existing socket:", e);
        }
    }

    try {
        socket = new WebSocket("ws://localhost:8001");

        socket.onopen = function(event) {
            server_available = true;
            reconnectAttempts = 0;
            updateStatus("Server connected");
            console.log("WebSocket connection established");
        };

        socket.onmessage = function(event) {
            try {
                let data = JSON.parse(event.data);
                if (data.type === 'fullSentence') {
                    fullSentences.push(data.text);
                    updateActiveFieldWithRecognition(data.text);
                    displayRealtimeText("", displayDiv);
                    document.getElementById('confirmationMessage').textContent =
                        `Was this correctly recognized? (RTF: ${data.rtf.toFixed(2)})`;
                    console.log("Received transcription:", data.text);
                    // Playing the text recieved
                    announce(data.text);
                
                } else if (data.type === 'error') {
                    updateStatus(`Error: ${data.message}`);
                    console.error("Server error:", data.message);
                }
            } catch (e) {
                console.error("Error processing message:", e, event.data);
            }
        };

        socket.onclose = function(event) {
            server_available = false;
            console.log("WebSocket connection closed:", event.code, event.reason);
            updateStatus("Server disconnected");

            if (isRecording) {
                stopRecording();
            }

            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(`Connection closed. Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
                reconnectTimeout = setTimeout(connectToServer, Math.min(1000 * Math.pow(2, reconnectAttempts), 16000));
            } else {
                console.log("Max reconnect attempts reached. Stopping reconnection.");
                updateStatus("Failed to reconnect to server after maximum attempts.");
            }
        };

        socket.onerror = function(error) {
            console.error("WebSocket error:", error);
        };
    } catch (e) {
        console.error("Error creating WebSocket:", e);
        server_available = false;
    }
}

// Initialize WebAudio context (will be created on first user interaction)
function initAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        console.log('Audio context initialized');
    }
    return audioContext;
}

function displayRealtimeText(realtimeText, displayDiv) {
    let displayedText = fullSentences.map((sentence, index) => {
        return `<span class="${index % 2 === 0 ? 'yellow' : 'cyan'}">${sentence} </span>`;
    }).join('') + realtimeText;
    displayDiv.innerHTML = displayedText;
}

function updateStatus(message) {
    console.log("Status update:", message);
    if (!mic_available)
        displayRealtimeText("🎤 Please allow microphone access 🎤", displayDiv);
    else if (!server_available)
        displayRealtimeText("🖥️ Please start the recognition server 🖥️", displayDiv);
    else if (message)
        displayRealtimeText(message, displayDiv);
}

function updateActiveFieldWithRecognition(text) {
    const activeField = document.getElementById(activeFieldId);
    if (activeField) {
        activeField.value = text; // Replace mode
    }
}

function startRecording() {
    console.log("Attempting to start recording");
    if (!mic_available) {
        alert("Microphone access is not available. Please check your browser permissions.");
        return;
    }

    if (!server_available) {
        alert("Server connection is not available. Please ensure the ASR server is running.");
        return;
    }

    if (isRecording) {
        console.log("Already recording, ignoring start request");
        return;
    }

    isRecording = true;
    document.getElementById('startRecording').disabled = true;
    document.getElementById('stopRecording').disabled = false;
    fullSentences = [];
    audioChunks = [];
    displayRealtimeText("Listening...", displayDiv);
    document.getElementById(activeFieldId + 'Group').classList.add('recording');

    if (stream) {
        startAudioProcessing();
    } else {
        console.log("Requesting microphone access");
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(str => {
                console.log("Microphone access granted");
                stream = str;
                mic_available = true;
                startAudioProcessing();
            })
            .catch(e => {
                console.error("Error getting audio stream:", e);
                updateStatus("Failed to access microphone");
                isRecording = false;
                document.getElementById('startRecording').disabled = false;
                document.getElementById('stopRecording').disabled = true;
            });
    }
}

function startAudioProcessing() {
    console.log("Starting audio processing");
    try {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

        mediaRecorder.ondataavailable = function(e) {
            if (e.data.size > 0) {
                audioChunks.push(e.data);
                if (socket && socket.readyState === WebSocket.OPEN) {
                    console.log("Sending audio chunk, size:", e.data.size);
                    socket.send(e.data); // Send each chunk immediately
                } else {
                    console.error("Cannot send audio chunk: WebSocket not open");
                    updateStatus("Cannot send audio: Server not connected. Attempting to reconnect...");
                    connectToServer();
                }
            }
        };

        mediaRecorder.onerror = function(e) {
            console.error("MediaRecorder error:", e);
        };

        mediaRecorder.start(100); // Capture data every 100ms
        console.log("MediaRecorder started");
    } catch (e) {
        console.error("Error starting MediaRecorder:", e);
        updateStatus("Failed to start recording");
        isRecording = false;
        document.getElementById('startRecording').disabled = false;
        document.getElementById('stopRecording').disabled = true;
    }
}

function stopRecording() {
    console.log("Stopping recording");
    if (!isRecording) {
        console.log("Not recording, ignoring stop request");
        return;
    }

    isRecording = false;
    document.getElementById('startRecording').disabled = false;
    document.getElementById('stopRecording').disabled = true;
    document.getElementById(activeFieldId + 'Group').classList.remove('recording');

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        try {
            mediaRecorder.stop();
            console.log("MediaRecorder stopped");

            mediaRecorder.onstop = function() {
                console.log("Processing recorded audio chunks:", audioChunks.length);
                if (audioChunks.length === 0) {
                    updateStatus("No audio recorded");
                    return;
                }

                // Send stop signal
                if (socket && socket.readyState === WebSocket.OPEN) {
                    console.log("Sending stop signal");
                    socket.send(JSON.stringify({ type: "stop" }));
                    displayRealtimeText("Processing audio...", displayDiv);
                } else {
                    console.error("Cannot send stop signal: WebSocket not open");
                    updateStatus("Cannot send stop signal: Server not connected. Attempting to reconnect...");
                    connectToServer();
                }
                audioChunks = []; // Clear chunks after sending
            };
        } catch (e) {
            console.error("Error stopping MediaRecorder:", e);
        }
    } else {
        console.log("MediaRecorder not available or already inactive");
    }
}

async function correctString(inputString, action) {
      try {
        const response = await fetch('http://localhost:11434/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: 'gemma3:1b',
            prompt: `You are a string corrector. For the input string "${inputString}", perform the action: "${action}". Return only the corrected string. Example: input "Dipanshu", action "Remove i and replace it with ee" returns "Deepanshu".`,
            stream: false
          })
        });
        if (!response.ok) throw new Error('Failed to fetch');
        const data = await response.json();
        return data.response.trim();
      } catch (error) {
        console.error('Error:', error);
        return inputString;
      }
}

function announce(message){
    // Check if audio context is initialized must be done on user interaction
    initAudioContext();
            
    // Clear any existing audio queue
    audioQueue = [];
    isPlaying = false;

    // Close existing socket if any
    if (voiceSocket) {
        voiceSocket.close();
    }
    console.log("Announcing message:", message);
    // Hardcode the WebSocket URL
    const wsUrl = 'ws://localhost:8000/ws/stream';
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    console.log(`Current location: protocol=${location.protocol}, host=${location.host}, href=${location.href}`);
    // Connect to WebSocket server
    voiceSocket = new WebSocket(wsUrl);
    voiceSocket.onopen = function() {
        console.log('Connected. Requesting audio stream...');
        
        // Send synthesis request
        voiceSocket.send(JSON.stringify({
            text: message,
            voice: "af_nicole",
            speed: parseFloat(1.0),
            language: "en-us"
        }));
    };
    
    voiceSocket.onmessage = async function(event) {
        // Make sure we received binary data
        if (event.data instanceof Blob) {
            // Convert blob to array buffer
            const arrayBuffer = await event.data.arrayBuffer();
            
            // Add to queue and start playing if not already playing
            audioQueue.push(arrayBuffer);
            console.log(`Received audio chunk (${(arrayBuffer.byteLength / 1024).toFixed(1)} KB)`);
            
            if (!isPlaying) {
                playNextInQueue();
            }
        } else {
            // Handle text messages (likely errors)
            console.log(`Server message: ${event.data}`);
        }
    };
    
    voiceSocket.onclose = function(event) {
        if (event.wasClean) {
            console.log(`Connection closed cleanly, code=${event.code} reason=${event.reason}`);
        } else {
            console.log('Connection lost');
        }
    };
    
    voiceSocket.onerror = function(error) {
        console.log(`WebSocket error: ${error.message}`);
    };
        
}

function askCorrection() {
    console.log("Asking for correction");
    isAskingCorrection = true;
    
}
function moveToNextField() {
    console.log("Moving to next field from", activeFieldId);
    document.getElementById(activeFieldId).classList.remove('active-field');
    document.getElementById(activeFieldId + 'Group').classList.remove('recording');
    const currentIndex = formFields.indexOf(activeFieldId);
    if (currentIndex < formFields.length - 1) {
        activeFieldId = formFields[currentIndex + 1];
    } else {
        activeFieldId = formFields[0];
    }
    document.getElementById(activeFieldId).classList.add('active-field');
    if (isRecording) {
        document.getElementById(activeFieldId + 'Group').classList.add('recording');
    }
    document.getElementById(activeFieldId).focus();
    fullSentences = [];
    displayRealtimeText(`Now recording for ${activeFieldId}...`, displayDiv);
    document.getElementById('confirmationMessage').textContent = "";
    console.log("New active field:", activeFieldId);
}

// Play next audio chunk in queue
async function playNextInQueue() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        setStatus('Playback complete');
        return;
    }
    
    isPlaying = true;
    const arrayBuffer = audioQueue.shift();
    
    try {
        // Decode the audio data
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        
        // Create a source node
        currentSource = audioContext.createBufferSource();
        currentSource.buffer = audioBuffer;
        
        // Connect to audio output
        currentSource.connect(audioContext.destination);
        
        // Play the audio
        currentSource.start(0);
        setStatus(`Playing audio (${audioQueue.length} chunks remaining in queue)`);
        
        // When this chunk finishes playing, play the next one
        currentSource.onended = function() {
            currentSource = null;
            playNextInQueue();
        };
        
    } catch (error) {
        console.log(`Error decoding audio: ${error.message}`);
        // Try to continue with next chunk
        playNextInQueue();
    }
}

// Initial setup
console.log("Initializing application");
connectToServer();

// Request microphone access
console.log("Requesting initial microphone access");
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(str => {
        stream = str;
        mic_available = true;
        console.log("Microphone access granted during initialization");
        updateStatus("Microphone access granted. Ready to start recording.");
    })
    .catch(e => {
        console.error("Error getting audio stream during initialization:", e);
        updateStatus("Failed to access microphone. Please check your settings.");
    });

// Setup periodic server connection check
setInterval(() => {
    if (!server_available && !reconnectTimeout) {
        console.log("Server check: not connected, attempting to connect");
        connectToServer();
    }
}, serverCheckInterval);

// Event listeners
document.getElementById('startRecording').addEventListener('click', startRecording);
document.getElementById('stopRecording').addEventListener('click', stopRecording);
document.getElementById('lookGood').addEventListener('click', moveToNextField);
document.getElementById('askCorrect').addEventListener('click', askCorrection);
document.getElementById('voiceForm').addEventListener('submit', function(e) {
    e.preventDefault();
    console.log("Form submission prevented");
});