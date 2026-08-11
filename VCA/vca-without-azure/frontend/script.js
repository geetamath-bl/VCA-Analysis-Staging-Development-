const audioFileInput = document.getElementById('audioFile');
const fileInfo = document.getElementById('fileInfo');
const fileNameSpan = document.getElementById('fileName');
const fileSizeSpan = document.getElementById('fileSize');
const btnAnalyze = document.getElementById('btnAnalyze');
const resultsSection = document.getElementById('resultsSection');

let selectedFile = null;

audioFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        selectedFile = e.target.files[0];
        
        fileNameSpan.textContent = selectedFile.name;
        fileSizeSpan.textContent = (selectedFile.size / (1024 * 1024)).toFixed(2) + ' MB';
        
        fileInfo.classList.remove('hidden');
        btnAnalyze.disabled = false;
    }
});

btnAnalyze.addEventListener('click', async () => {
    if (!selectedFile) return;

    btnAnalyze.disabled = true;
    btnAnalyze.textContent = "⏳ Analyzing Audio...";
    resultsSection.classList.add('hidden');

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
        const response = await fetch("/vca/analyze", {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Server returned status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.status === "success") {
            displayResults(data);
        } else {
            alert("Analysis failed. Please check logs.");
        }
    } catch (error) {
        alert("Error analyzing file: " + error.message);
    } finally {
        btnAnalyze.disabled = false;
        btnAnalyze.textContent = "⚡ Analyze Audio";
    }
});

function displayResults(data) {
    const report = data.report;
    
    document.getElementById('resFileName').textContent = data.filename;
    document.getElementById('overallScore').textContent = report.overall_score;
    document.getElementById('ratingBadge').textContent = report.rating;

    document.getElementById('paceScore').textContent = report.pace_score;
    document.getElementById('fluencyScore').textContent = report.fluency_score;
    document.getElementById('fillerScore').textContent = report.filler_score;
    document.getElementById('expressivenessScore').textContent = report.expressiveness_score;
    document.getElementById('vocabScore').textContent = report.vocab_grammar_score;

    resultsSection.classList.remove('hidden');
}