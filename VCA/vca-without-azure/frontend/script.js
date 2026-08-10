document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const btnBrowse = document.getElementById("btnBrowse");
    const audioInput = document.getElementById("audioInput");
    const fileNameDisplay = document.getElementById("fileNameDisplay");
    const statusCheck = document.getElementById("statusCheck");
    const btnAnalyze = document.getElementById("btnAnalyze");
    const btnText = document.getElementById("btnText");
    const resultsSection = document.getElementById("resultsSection");

    // Max allowed size before triggering client-side compression (5MB in bytes)
    const MAX_SIZE_BYTES = 5 * 1024 * 1024; 

    // 1. Browse Button Click Listener
    btnBrowse.addEventListener("click", () => {
        audioInput.click();
    });

    // 2. File Input Change Listener
    audioInput.addEventListener("change", function () {
        if (this.files && this.files.length > 0) {
            const file = this.files[0];
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            fileNameDisplay.textContent = `${file.name} (${sizeMB} MB)`;
            if (statusCheck) statusCheck.style.display = "inline-block";
            btnAnalyze.disabled = false;
        } else {
            fileNameDisplay.textContent = "No file selected";
            if (statusCheck) statusCheck.style.display = "none";
            btnAnalyze.disabled = true;
        }
    });

    // 3. Analyze Button Click Handler
    btnAnalyze.addEventListener("click", async () => {
        let file = audioInput.files[0];
        if (!file) {
            alert("Please select an audio file first!");
            return;
        }

        btnAnalyze.disabled = true;

        try {
            // Check file size: If larger than 5MB, compress on frontend
            if (file.size > MAX_SIZE_BYTES) {
                btnText.textContent = "Compressing large file in browser...";
                console.log(`⚠️ File size (${(file.size / (1024 * 1024)).toFixed(2)} MB) exceeds 5MB. Compressing in frontend...`);
                file = await compressAudioFrontend(file);
                console.log(`⚡ Compression completed! New size: ${(file.size / (1024 * 1024)).toFixed(2)} MB`);
            }

            btnText.textContent = "Analyzing Audio...";
            await analyzeAudio(file);

        } catch (err) {
            console.error("❌ Process Error:", err);
            alert("Error processing file: " + err.message);
        } finally {
            btnAnalyze.disabled = false;
            btnText.textContent = "Analyze Audio";
        }
    });

    // 4. Client-side Audio Compression (Downsample to 16kHz Mono WAV using Web Audio API)
    async function compressAudioFrontend(file) {
        const arrayBuffer = await file.arrayBuffer();
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        // Decode raw file to AudioBuffer
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        audioCtx.close();

        // Target sample rate for speech processing (16000 Hz Mono)
        const targetSampleRate = 16000;
        const offlineCtx = new OfflineAudioContext(1, audioBuffer.duration * targetSampleRate, targetSampleRate);

        const source = offlineCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(offlineCtx.destination);
        source.start(0);

        const renderedBuffer = await offlineCtx.startRendering();
        
        // Convert to WAV Blob
        const wavBlob = audioBufferToWavBlob(renderedBuffer);
        
        // Return a File Object
        const compressedFileName = file.name.substring(0, file.name.lastIndexOf('.')) + "_compressed.wav";
        return new File([wavBlob], compressedFileName, { type: "audio/wav" });
    }

    // Helper: Encode AudioBuffer to WAV format
    function audioBufferToWavBlob(buffer) {
        const numOfChan = buffer.numberOfChannels;
        const length = buffer.length * numOfChan * 2 + 44;
        const outBuffer = new ArrayBuffer(length);
        const view = new DataView(outBuffer);
        const channels = [];
        let sample = 0;
        let offset = 0;
        let pos = 0;

        function setUint16(data) { view.setUint16(pos, data, true); pos += 2; }
        function setUint32(data) { view.setUint32(pos, data, true); pos += 4; }

        // WAV Header
        setUint32(0x46464952);                         // "RIFF"
        setUint32(length - 8);                         // file length - 8
        setUint32(0x45564157);                         // "WAVE"
        setUint32(0x20746d66);                         // "fmt " chunk
        setUint32(16);                                 // length = 16
        setUint16(1);                                  // PCM (uncompressed)
        setUint16(numOfChan);                          // mono
        setUint32(buffer.sampleRate);                  // sample rate
        setUint32(buffer.sampleRate * 2 * numOfChan);  // byte rate
        setUint16(numOfChan * 2);                      // block align
        setUint16(16);                                 // 16-bit
        setUint32(0x61746164);                         // "data" chunk
        setUint32(length - pos - 4);                   // chunk length

        for (let i = 0; i < buffer.numberOfChannels; i++) {
            channels.push(buffer.getChannelData(i));
        }

        while (offset < buffer.length) {
            for (let i = 0; i < numOfChan; i++) {
                sample = Math.max(-1, Math.min(1, channels[i][offset]));
                sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
                view.setInt16(pos, sample, true);
                pos += 2;
            }
            offset++;
        }

        return new Blob([outBuffer], { type: "audio/wav" });
    }

    // 5. Send POST Request to Backend Endpoint
    async function analyzeAudio(audioFile) {
        const formData = new FormData();
        formData.append("file", audioFile);

        // Automatically selects local backend URL during dev, and Vercel relative path on production
        const endpoint = (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost") 
            ? "http://127.0.0.1:8000/vca/analyze" 
            : "/vca/analyze";

        const response = await fetch(endpoint, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Server status error: ${response.status}`);
        }

        const data = await response.json();
        renderResults(data);
    }

    // 6. Update Dashboard UI
    function renderResults(data) {
        console.log("🎨 [STEP 3: FRONTEND] Updating Dashboard...");

        const overallScore = data.overall_score ?? 0;
        const ratingLabel = data.rating ?? "N/A";
        const pace = data.pace_score ?? 0;
        const fluency = data.fluency_score ?? 0;
        const vocab = data.vocab_grammar_score ?? 0;
        const expressiveness = data.expressiveness_score ?? 0;

        if (resultsSection) {
            resultsSection.style.display = "block";
        }

        const overallElem = document.getElementById("overallScoreNum");
        if (overallElem) overallElem.textContent = overallScore;

        const ratingElem = document.getElementById("ratingLabel");
        if (ratingElem) ratingElem.textContent = ratingLabel;

        const paceElem = document.getElementById("paceScore");
        if (paceElem) paceElem.textContent = pace;

        const fluencyElem = document.getElementById("fluencyScore");
        if (fluencyElem) fluencyElem.textContent = fluency;

        const vocabElem = document.getElementById("vocabScore");
        if (vocabElem) vocabElem.textContent = vocab;

        const expressElem = document.getElementById("expressScore");
        if (expressElem) expressElem.textContent = expressiveness;

        const paceBar = document.getElementById("paceBar");
        if (paceBar) paceBar.style.width = `${pace}%`;

        const fluencyBar = document.getElementById("fluencyBar");
        if (fluencyBar) fluencyBar.style.width = `${fluency}%`;

        const vocabBar = document.getElementById("vocabBar");
        if (vocabBar) vocabBar.style.width = `${vocab}%`;

        const expressBar = document.getElementById("expressBar");
        if (expressBar) expressBar.style.width = `${expressiveness}%`;

        console.log("✅ [STEP 4: FRONTEND] Complete.");
    }
});