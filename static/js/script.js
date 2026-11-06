// ======================================
// TRACKBACK - TEXT AND VOICE INVESTIGATION
// ======================================

let mediaRecorder = null;
let audioChunks = [];
let recordedAudio = null;
let audioURL = null;


// ======================================
// DISPLAY INVESTIGATION RESULTS
// ======================================

function displayResults(data) {

    document.getElementById("status").textContent =
        data.status || "Unknown";

    document.getElementById("keywords").textContent =
        data.keywords || "Not available";

    document.getElementById("analysis").textContent =
        data.analysis || "";

    document.getElementById("aiAnalysis").textContent =
        data.ai_analysis || "AI analysis unavailable.";

    const evidenceBox = document.getElementById("evidence");
    evidenceBox.innerHTML = "";

    if (data.evidence && data.evidence.length > 0) {

        data.evidence.forEach(item => {

            const card = document.createElement("div");

            card.style.padding = "15px";
            card.style.margin = "12px 0";
            card.style.border = "1px solid #888";
            card.style.borderRadius = "10px";

            const title = document.createElement("h4");
            title.textContent = item.title;

            const snippet = document.createElement("p");
            snippet.textContent = item.snippet || "";

            const sourceType = document.createElement("p");
            sourceType.textContent =
                "Source category: " + (item.source_type || "Unknown");

            const content = document.createElement("p");
            content.textContent = item.content
                ? item.content.substring(0, 400)
                : "Could not retrieve page content.";

            const link = document.createElement("a");
            link.href = item.url;
            link.textContent = "View Source";
            link.target = "_blank";
            link.rel = "noopener noreferrer";

            card.appendChild(title);
            card.appendChild(snippet);
            card.appendChild(sourceType);
            card.appendChild(content);
            card.appendChild(link);

            evidenceBox.appendChild(card);

        });

    } else {

        evidenceBox.textContent =
            "No search results found. Try again later.";

    }

    document.getElementById("results").style.display = "block";
}


// ======================================
// TEXT INVESTIGATION
// ======================================

async function investigateClaim() {

    const claim = document.getElementById("claimInput").value.trim();

    const button = document.getElementById("investigateBtn");
    const error = document.getElementById("error");
    const results = document.getElementById("results");

    error.textContent = "";
    results.style.display = "none";

    if (!claim) {
        error.textContent = "Please enter a claim first!";
        return;
    }

    button.disabled = true;
    button.textContent = "Investigating...";

    try {

        const response = await fetch("/api/investigate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                claim: claim
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Investigation failed.");
        }

        displayResults(data);

    } catch (err) {

        error.textContent = err.message;

    } finally {

        button.disabled = false;
        button.textContent = "Investigate Claim →";

    }
}


// ======================================
// START VOICE RECORDING
// ======================================

async function startRecording() {

    const status = document.getElementById("recordingStatus");
    const startBtn = document.getElementById("startRecordBtn");
    const stopBtn = document.getElementById("stopRecordBtn");
    const voiceError = document.getElementById("voiceError");

    voiceError.textContent = "";

    if (!navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia ||
        !window.MediaRecorder) {

        voiceError.textContent =
            "Your browser does not support voice recording.";

        return;
    }

    try {

        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });

        let options = {};

        const formats = [
            "audio/webm;codecs=opus",
            "audio/webm",
            "audio/ogg;codecs=opus"
        ];

        for (const format of formats) {

            if (MediaRecorder.isTypeSupported(format)) {
                options.mimeType = format;
                break;
            }

        }

        mediaRecorder = new MediaRecorder(stream, options);

        audioChunks = [];
        recordedAudio = null;

        mediaRecorder.ondataavailable = function(event) {

            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }

        };

        mediaRecorder.onstop = function() {

            const mimeType =
                mediaRecorder.mimeType || "audio/webm";

            recordedAudio = new Blob(audioChunks, {
                type: mimeType
            });

            if (audioURL) {
                URL.revokeObjectURL(audioURL);
            }

            audioURL = URL.createObjectURL(recordedAudio);

            const playback = document.getElementById("audioPlayback");

            playback.src = audioURL;
            playback.style.display = "block";

            document.getElementById("deleteRecordBtn").style.display =
                "inline-block";

            document.getElementById("investigateVoiceBtn").disabled =
                false;

            status.textContent = "Recording completed! Listen before submitting.";

            stream.getTracks().forEach(track => track.stop());

        };

        mediaRecorder.start();

        startBtn.disabled = true;
        stopBtn.disabled = false;

        document.getElementById("audioPlayback").style.display = "none";
        document.getElementById("deleteRecordBtn").style.display = "none";
        document.getElementById("investigateVoiceBtn").disabled = true;
        document.getElementById("transcriptBox").style.display = "none";
        document.getElementById("results").style.display = "none";

        status.textContent = "🔴 Recording... Speak now!";

    } catch (error) {

        voiceError.textContent =
            "Microphone access failed. Please allow microphone permission.";

        console.error("Recording error:", error);

    }

}


// ======================================
// STOP VOICE RECORDING
// ======================================

function stopRecording() {

    if (mediaRecorder && mediaRecorder.state === "recording") {

        mediaRecorder.stop();

        document.getElementById("startRecordBtn").disabled = false;
        document.getElementById("stopRecordBtn").disabled = true;

    }

}


// ======================================
// DELETE RECORDING
// ======================================

function deleteRecording() {

    recordedAudio = null;

    if (audioURL) {
        URL.revokeObjectURL(audioURL);
        audioURL = null;
    }

    document.getElementById("audioPlayback").removeAttribute("src");
    document.getElementById("audioPlayback").style.display = "none";

    document.getElementById("deleteRecordBtn").style.display = "none";
    document.getElementById("investigateVoiceBtn").disabled = true;

    document.getElementById("recordingStatus").textContent =
        "Recording deleted. You can record again.";

    document.getElementById("transcriptBox").style.display = "none";
    document.getElementById("results").style.display = "none";

}


// ======================================
// INVESTIGATE VOICE
// ======================================

async function investigateVoice() {

    const button = document.getElementById("investigateVoiceBtn");
    const loading = document.getElementById("voiceLoading");
    const error = document.getElementById("voiceError");

    error.textContent = "";

    if (!recordedAudio) {

        error.textContent = "Please record a voice message first.";
        return;

    }

    button.disabled = true;
    button.textContent = "Investigating Voice...";
    loading.style.display = "block";

    document.getElementById("results").style.display = "none";
    document.getElementById("transcriptBox").style.display = "none";

    try {

        let extension = "webm";

        if (recordedAudio.type.includes("ogg")) {
            extension = "ogg";
        }

        const formData = new FormData();

        formData.append(
            "audio",
            recordedAudio,
            "trackback_recording." + extension
        );

        const response = await fetch("/api/voice-investigate", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Voice investigation failed.");
        }

        // Display the converted speech
        document.getElementById("transcriptText").textContent =
            data.transcript || "No transcript returned.";

        document.getElementById("transcriptBox").style.display = "block";

        // Display investigation results
        displayResults(data);

    } catch (err) {

        error.textContent = err.message;

    } finally {

        loading.style.display = "none";
        button.disabled = false;
        button.textContent = "🔍 Investigate Voice";

    }

}