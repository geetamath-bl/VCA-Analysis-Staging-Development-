// UPLOAD SIZE LIMITS
// Vercel rejects request bodies over 4.5 MB (HTTP 413), so audio is converted
// to mono 16-bit WAV at the highest sample rate that keeps it under this size.
const MAX_UPLOAD_BYTES = 4.2 * 1024 * 1024;        // margin under 4.5 MB for form overhead
const BEST_SAMPLE_RATE = 16000;
const MIN_SAMPLE_RATE = 8000;                      // still enough for speech and pitch analysis
const WAV_HEADER_BYTES = 44;
const MAX_AUDIO_SECONDS = Math.floor((MAX_UPLOAD_BYTES - WAV_HEADER_BYTES) / (MIN_SAMPLE_RATE * 2));
const MAX_AUDIO_LABEL = formatDuration(MAX_AUDIO_SECONDS);

function formatDuration(totalSeconds) {
    const mins = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
    const secs = String(Math.floor(totalSeconds % 60)).padStart(2, '0');
    return `${mins}:${secs}`;
}

// TAB NAVIGATION SETUP
const tabUploadBtn = document.getElementById('tabUploadBtn');
const tabRecordBtn = document.getElementById('tabRecordBtn');
const tabUploadContent = document.getElementById('tabUploadContent');
const tabRecordContent = document.getElementById('tabRecordContent');

tabUploadBtn.addEventListener('click', () => {
    tabUploadBtn.classList.add('active');
    tabRecordBtn.classList.remove('active');
    tabUploadContent.classList.add('active');
    tabRecordContent.classList.remove('active');
});

tabRecordBtn.addEventListener('click', () => {
    tabRecordBtn.classList.add('active');
    tabUploadBtn.classList.remove('active');
    tabRecordContent.classList.add('active');
    tabUploadContent.classList.remove('active');
});

// FILE UPLOAD LOGIC
const audioFileInput = document.getElementById('audioFile');
const fileInfo = document.getElementById('fileInfo');
const fileNameSpan = document.getElementById('fileName');
const fileSizeSpan = document.getElementById('fileSize');
const btnAnalyzeUpload = document.getElementById('btnAnalyzeUpload');
const resultsSection = document.getElementById('resultsSection');
const statusBox = document.getElementById('statusBox');
const statusText = document.getElementById('statusText');

let selectedFile = null;

audioFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        selectedFile = e.target.files[0];
        fileNameSpan.textContent = selectedFile.name;
        fileSizeSpan.textContent = (selectedFile.size / (1024 * 1024)).toFixed(2) + ' MB';
        fileInfo.classList.remove('hidden');
        btnAnalyzeUpload.disabled = false;
        if (statusBox) statusBox.classList.add('hidden');
    }
});

btnAnalyzeUpload.addEventListener('click', async () => {
    if (selectedFile) await processAndSendFile(selectedFile, btnAnalyzeUpload);
});

// LIVE AUDIO RECORDING LOGIC
const btnStartRecord = document.getElementById('btnStartRecord');
const btnStopRecord = document.getElementById('btnStopRecord');
const recordTimer = document.getElementById('recordTimer');
const audioPreview = document.getElementById('audioPreview');
const recordInfo = document.getElementById('recordInfo');
const btnDownloadRecord = document.getElementById('btnDownloadRecord');
const btnAnalyzeRecord = document.getElementById('btnAnalyzeRecord');

let mediaRecorder = null;
let audioChunks = [];
let timerInterval = null;
let secondsRecorded = 0;
let recordedWavFile = null;

btnStartRecord.addEventListener('click', async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);

        mediaRecorder.onstop = async () => {
            const rawBlob = new Blob(audioChunks, { type: 'audio/webm' });
            
            showStatus("⚙️ Encoding audio to 16kHz .wav format...");
            recordedWavFile = await convertBlobToWav(rawBlob);
            
            const wavUrl = URL.createObjectURL(recordedWavFile);
            audioPreview.src = wavUrl;
            audioPreview.classList.remove('hidden');
            
            btnDownloadRecord.href = wavUrl;
            btnDownloadRecord.download = "recorded_audio.wav";
            btnDownloadRecord.classList.remove('hidden');
            btnAnalyzeRecord.classList.remove('hidden');
            recordInfo.classList.remove('hidden');
            
            statusBox.classList.add('hidden');
        };

        mediaRecorder.start();
        btnStartRecord.classList.add('hidden');
        btnStopRecord.classList.remove('hidden');
        btnDownloadRecord.classList.add('hidden');
        btnAnalyzeRecord.classList.add('hidden');
        audioPreview.classList.add('hidden');
        recordInfo.classList.add('hidden');

        // Start Timer
        secondsRecorded = 0;
        recordTimer.textContent = `00:00 / ${MAX_AUDIO_LABEL}`;
        timerInterval = setInterval(() => {
            secondsRecorded++;
            recordTimer.textContent = `${formatDuration(secondsRecorded)} / ${MAX_AUDIO_LABEL}`;

            // Stop automatically at the longest length the server can accept
            if (secondsRecorded >= MAX_AUDIO_SECONDS) {
                btnStopRecord.click();
                showStatus(`⏹️ Recording stopped at the ${MAX_AUDIO_LABEL} maximum.`);
            }
        }, 1000);

    } catch (err) {
        alert("Microphone access denied or not supported: " + err.message);
    }
});

btnStopRecord.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
        clearInterval(timerInterval);
        btnStopRecord.classList.add('hidden');
        btnStartRecord.classList.remove('hidden');
    }
});

btnAnalyzeRecord.addEventListener('click', async () => {
    if (recordedWavFile) await processAndSendFile(recordedWavFile, btnAnalyzeRecord);
});

// FILE CONVERSION & SUBMISSION PROCESSOR
async function processAndSendFile(file, buttonElement) {
    buttonElement.disabled = true;
    resultsSection.classList.add('hidden');

    try {
        const fileToSend = await prepareForUpload(file);

        showStatus("⚡ Processing analysis... This can take up to a minute.");
        buttonElement.textContent = "⏳ Analyzing...";

        const formData = new FormData();
        formData.append("file", fileToSend);

        let response;
        try {
            response = await fetch("/vca/analyze", {
                method: "POST",
                body: formData
            });
        } catch (networkError) {
            throw new Error("Could not reach the server. Please check your internet connection and try again.");
        }

        if (!response.ok) throw new Error(await describeServerError(response));

        const data = await response.json();
        if (data.status === "success") {
            statusBox.classList.add('hidden');
            displayResults(data);
        } else {
            throw new Error("Analysis did not complete. Please try again.");
        }

    } catch (error) {
        showStatus("❌ " + error.message);
    } finally {
        buttonElement.disabled = false;
        buttonElement.textContent = "⚡ Analyze Audio";
    }
}

function showStatus(msg) {
    statusText.textContent = msg;
    statusBox.classList.remove('hidden');
}

// Returns a WAV file small enough for the server, converting only when needed.
async function prepareForUpload(file) {
    const isWav = file.name.toLowerCase().endsWith('.wav');
    if (isWav && file.size <= MAX_UPLOAD_BYTES) return file;

    showStatus("🔄 Preparing audio for upload...");
    const audioBuffer = await decodeAudio(file);
    const duration = audioBuffer.duration;

    if (duration > MAX_AUDIO_SECONDS) {
        throw new Error(
            `This audio is ${formatDuration(duration)} long. The maximum is ${MAX_AUDIO_LABEL}. ` +
            `Please upload or record a shorter clip.`
        );
    }

    // Highest sample rate (up to 16 kHz) that keeps the WAV under the size limit
    const fittingRate = Math.floor((MAX_UPLOAD_BYTES - WAV_HEADER_BYTES) / (duration * 2));
    const sampleRate = Math.max(MIN_SAMPLE_RATE, Math.min(BEST_SAMPLE_RATE, fittingRate));
    return await renderToWav(audioBuffer, sampleRate, file.name);
}

// Turns a failed response into a clear message, using the server's detail when available.
async function describeServerError(response) {
    let detail = "";
    try {
        const body = await response.json();
        if (typeof body.detail === "string") detail = body.detail;
    } catch (e) { /* response was not JSON */ }

    switch (response.status) {
        case 413:
            return `The audio file is too large to upload. Please use a clip shorter than ${MAX_AUDIO_LABEL}.`;
        case 429:
            return detail || "The analysis service is busy right now. Please wait a minute and try again.";
        case 400:
            return detail || "This audio file could not be read. Please try a different file.";
        case 504:
            return "The analysis took too long. Please try a shorter clip.";
        default:
            return detail
                ? `Analysis failed: ${detail}`
                : `Analysis failed (server error ${response.status}). Please try again.`;
    }
}

// WEB AUDIO API PCM CONVERTER TO MONO WAV
async function convertBlobToWav(blob) {
    const file = new File([blob], "recorded_audio.webm", { type: blob.type });
    return await convertToWav(file);
}

async function convertToWav(file) {
    const audioBuffer = await decodeAudio(file);
    return await renderToWav(audioBuffer, BEST_SAMPLE_RATE, file.name);
}

async function decodeAudio(file) {
    const arrayBuffer = await file.arrayBuffer();
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    try {
        return await audioCtx.decodeAudioData(arrayBuffer);
    } catch (e) {
        throw new Error("This file's audio could not be read. Please try a WAV, MP3 or M4A file.");
    } finally {
        audioCtx.close();
    }
}

async function renderToWav(audioBuffer, targetSampleRate, originalFileName) {
    const targetChannels = 1;

    const offlineCtx = new OfflineAudioContext(
        targetChannels,
        Math.ceil(audioBuffer.duration * targetSampleRate),
        targetSampleRate
    );

    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineCtx.destination);
    source.start(0);

    const renderedBuffer = await offlineCtx.startRendering();
    const wavBlob = bufferToWave(renderedBuffer);

    const originalName = originalFileName.substring(0, originalFileName.lastIndexOf('.')) || originalFileName;
    return new File([wavBlob], `${originalName}_converted.wav`, { type: 'audio/wav' });
}

function bufferToWave(abuffer) {
    let numOfChan = abuffer.numberOfChannels,
        length = abuffer.length * numOfChan * 2 + 44,
        buffer = new ArrayBuffer(length),
        view = new DataView(buffer),
        channels = [], i, sample, offset = 0, pos = 0;

    setUint32(0x46464952); // "RIFF"
    setUint32(length - 8); 
    setUint32(0x45564157); // "WAVE"
    setUint32(0x20746d66); // "fmt " chunk
    setUint32(16);         // length = 16
    setUint16(1);          // PCM
    setUint16(numOfChan);
    setUint32(abuffer.sampleRate);
    setUint32(abuffer.sampleRate * 2 * numOfChan);
    setUint16(numOfChan * 2);
    setUint16(16);
    setUint32(0x61746164); // "data" chunk
    setUint32(length - pos - 4);

    for (i = 0; i < abuffer.numberOfChannels; i++) {
        channels.push(abuffer.getChannelData(i));
    }

    while (pos < length) {
        for (i = 0; i < numOfChan; i++) {
            sample = Math.max(-1, Math.min(1, channels[i][offset]));
            sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
            view.setInt16(pos, sample, true);
            pos += 2;
        }
        offset++;
    }

    return new Blob([buffer], { type: "audio/wav" });

    function setUint16(data) { view.setUint16(pos, data, true); pos += 2; }
    function setUint32(data) { view.setUint32(pos, data, true); pos += 4; }
}

function displayResults(data) {
    const report = data.report;
    document.getElementById('resFileName').textContent = data.filename;
    
    // HIGHLIGHTED RATING TEXT & SMALL NUMERIC SUB-SCORE
    document.getElementById('ratingBadgeText').textContent = report.rating || "Excellent";
    document.getElementById('overallScore').textContent = report.overall_score;

    document.getElementById('paceScore').textContent = report.pace_score;
    document.getElementById('fluencyScore').textContent = report.fluency_score;
    document.getElementById('fillerScore').textContent = report.filler_score;
    document.getElementById('expressivenessScore').textContent = report.expressiveness_score;
    document.getElementById('vocabScore').textContent = report.vocab_grammar_score;

    resultsSection.classList.remove('hidden');
}