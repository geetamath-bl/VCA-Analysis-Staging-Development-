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
        recordTimer.textContent = "00:00";
        timerInterval = setInterval(() => {
            secondsRecorded++;
            const mins = String(Math.floor(secondsRecorded / 60)).padStart(2, '0');
            const secs = String(secondsRecorded % 60).padStart(2, '0');
            recordTimer.textContent = `${mins}:${secs}`;
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
        let fileToSend = file;
        const fileExt = file.name.split('.').pop().toLowerCase();
        const fileSizeMB = file.size / (1024 * 1024);

        if (fileExt !== 'wav') {
            showStatus(`🔄 Converting ${fileExt.toUpperCase()} file to .wav...`);
            fileToSend = await convertToWav(file);
        } else if (fileSizeMB > 3.0) {
            showStatus(`📉 Compressing ${fileSizeMB.toFixed(2)} MB .wav to under 3 MB...`);
            fileToSend = await convertToWav(file);
        }

        showStatus("⚡ Processing analysis... Please wait.");
        buttonElement.textContent = "⏳ Analyzing...";

        const formData = new FormData();
        formData.append("file", fileToSend);

        const response = await fetch("/vca/analyze", {
            method: "POST",
            body: formData
        });

        if (!response.ok) throw new Error(`Server returned status: ${response.status}`);

        const data = await response.json();
        if (data.status === "success") {
            statusBox.classList.add('hidden');
            displayResults(data);
        } else {
            alert("Analysis failed. Please check logs.");
        }

    } catch (error) {
        showStatus("❌ Error during processing: " + error.message);
        alert("Error analyzing file: " + error.message);
    } finally {
        buttonElement.disabled = false;
        buttonElement.textContent = "⚡ Analyze Audio";
    }
}

function showStatus(msg) {
    statusText.textContent = msg;
    statusBox.classList.remove('hidden');
}

// WEB AUDIO API PCM CONVERTER TO 16kHz MONO WAV
async function convertBlobToWav(blob) {
    const file = new File([blob], "recorded_audio.webm", { type: blob.type });
    return await convertToWav(file);
}

async function convertToWav(file) {
    const arrayBuffer = await file.arrayBuffer();
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    const targetSampleRate = 16000;
    const targetChannels = 1;

    const offlineCtx = new OfflineAudioContext(
        targetChannels,
        audioBuffer.duration * targetSampleRate,
        targetSampleRate
    );

    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineCtx.destination);
    source.start(0);

    const renderedBuffer = await offlineCtx.startRendering();
    const wavBlob = bufferToWave(renderedBuffer);

    const originalName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
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