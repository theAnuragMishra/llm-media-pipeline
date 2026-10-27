/**
 * Media Pipeline Web Studio Client
 * Manages job submission and real-time SSE/WebSocket event streaming.
 */

let activeStream = null;
let currentTaskId = null;

const form = document.getElementById("generateForm");
const topicInput = document.getElementById("topicInput");
const submitBtn = document.getElementById("submitBtn");
const btnSpinner = document.getElementById("btnSpinner");
const connectionStatus = document.getElementById("connectionStatus");
const currentStageText = document.getElementById("currentStageText");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");
const taskMetaLabel = document.getElementById("taskMetaLabel");
const logTerminal = document.getElementById("logTerminal");
const clearLogsBtn = document.getElementById("clearLogsBtn");
const videoPlayer = document.getElementById("courseVideoPlayer");
const videoPlaceholder = document.getElementById("videoPlaceholder");
const videoStatusBadge = document.getElementById("videoStatusBadge");
const artifactActions = document.getElementById("artifactActions");
const downloadBtn = document.getElementById("downloadBtn");
const directLinkBtn = document.getElementById("directLinkBtn");
const protocolSelect = document.getElementById("protocolSelect");
const scenesSelect = document.getElementById("scenesSelect");
const voiceSelect = document.getElementById("voiceSelect");

// Handle preset chips
document.querySelectorAll(".preset-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    topicInput.value = chip.dataset.topic;
    topicInput.focus();
  });
});

clearLogsBtn.addEventListener("click", () => {
  logTerminal.innerHTML = '<div class="text-slate-600">// Logs cleared.</div>';
});

function appendLog(message, stage = "INFO", isError = false) {
  const timestamp = new Date().toLocaleTimeString();
  const line = document.createElement("div");
  line.className = `flex items-start gap-2 ${isError ? "text-rose-400" : "text-slate-300"}`;

  const timeSpan = document.createElement("span");
  timeSpan.className = "text-slate-500 shrink-0";
  timeSpan.textContent = `[${timestamp}]`;

  const stageSpan = document.createElement("span");
  stageSpan.className = `font-bold shrink-0 ${isError ? "text-rose-400" : "text-brand-400"}`;
  stageSpan.textContent = `[${stage}]`;

  const msgSpan = document.createElement("span");
  msgSpan.textContent = message;

  line.appendChild(timeSpan);
  line.appendChild(stageSpan);
  line.appendChild(msgSpan);

  logTerminal.appendChild(line);
  logTerminal.scrollTop = logTerminal.scrollHeight;
}

function updateStageSteps(stage) {
  const stepMap = {
    "SCRIPT_GENERATION": "step-script",
    "AUDIO_SYNTHESIS": "step-audio",
    "SCENE_RENDERING": "step-visual",
    "FFMPEG_COMPOSITION": "step-ffmpeg",
    "UPLOAD_AND_STORAGE": "step-storage",
    "COMPLETED": "step-storage",
  };

  const allSteps = ["step-script", "step-audio", "step-visual", "step-ffmpeg", "step-storage"];
  const targetId = stepMap[stage];

  if (!targetId) return;

  let activeIndex = allSteps.indexOf(targetId);
  allSteps.forEach((id, idx) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (idx < activeIndex) {
      el.className = "p-2 rounded-lg border border-emerald-500/50 bg-emerald-500/10 text-emerald-400";
    } else if (idx === activeIndex) {
      el.className = "p-2 rounded-lg border border-brand-500 bg-brand-500/20 text-brand-300 animate-pulse";
    } else {
      el.className = "p-2 rounded-lg border border-slate-800/80 bg-slate-950/60 text-slate-500";
    }
  });
}

function updateProgress(eventData) {
  const { stage, progress_percent, message, video_url, error } = eventData;

  currentStageText.textContent = stage.replace(/_/g, " ");
  progressPercent.textContent = `${progress_percent}%`;
  progressBar.style.width = `${progress_percent}%`;

  updateStageSteps(stage);
  appendLog(message, stage, !!error);

  if (error) {
    videoStatusBadge.textContent = "Failed";
    videoStatusBadge.className = "text-xs px-2.5 py-1 rounded-full font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30";
    cleanupStream();
    return;
  }

  if (stage === "COMPLETED" && video_url) {
    videoStatusBadge.textContent = "Render Ready (1080p)";
    videoStatusBadge.className = "text-xs px-2.5 py-1 rounded-full font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";

    videoPlaceholder.classList.add("hidden");
    videoPlayer.classList.remove("hidden");
    videoPlayer.src = video_url;
    videoPlayer.load();

    artifactActions.classList.remove("hidden");
    downloadBtn.href = video_url;
    directLinkBtn.href = video_url;

    cleanupStream();
  }
}

function cleanupStream() {
  submitBtn.disabled = false;
  btnSpinner.classList.add("hidden");

  if (activeStream) {
    if (activeStream.close) activeStream.close();
    activeStream = null;
  }

  connectionStatus.innerHTML = `
    <span class="w-2 h-2 rounded-full bg-slate-500"></span>
    <span>Finished</span>
  `;
}

function connectSSE(sseUrl) {
  connectionStatus.innerHTML = `
    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
    <span class="text-emerald-400">SSE Connected</span>
  `;

  const eventSource = new EventSource(sseUrl);
  activeStream = eventSource;

  eventSource.addEventListener("progress", (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgress(data);
    } catch (err) {
      console.error("Failed to parse SSE payload", err);
    }
  });

  eventSource.addEventListener("error", (e) => {
    appendLog("SSE connection closed or reached end of stream", "STREAM");
    cleanupStream();
  });
}

function connectWebSocket(wsUrl) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const fullWsUrl = `${protocol}//${window.location.host}${wsUrl}`;

  connectionStatus.innerHTML = `
    <span class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
    <span class="text-indigo-400">WebSocket Connected</span>
  `;

  const ws = new WebSocket(fullWsUrl);
  activeStream = ws;

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgress(data);
    } catch (err) {
      console.error("Failed to parse WS payload", err);
    }
  };

  ws.onclose = () => {
    appendLog("WebSocket closed gracefully.", "STREAM");
    cleanupStream();
  };

  ws.onerror = (e) => {
    appendLog("WebSocket connection error", "STREAM", true);
    cleanupStream();
  };
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const topic = topicInput.value.trim();
  if (!topic) return;

  cleanupStream();

  // Reset UI
  submitBtn.disabled = true;
  btnSpinner.classList.remove("hidden");
  progressBar.style.width = "5%";
  progressPercent.textContent = "5%";
  currentStageText.textContent = "Dispatching...";
  videoPlaceholder.classList.remove("hidden");
  videoPlayer.classList.add("hidden");
  artifactActions.classList.add("hidden");
  videoStatusBadge.textContent = "Processing";
  videoStatusBadge.className = "text-xs px-2.5 py-1 rounded-full font-mono bg-brand-500/10 text-brand-400 border border-brand-500/30";

  appendLog(`Submitting job for topic: "${topic}"...`, "DISPATCH");

  try {
    const payload = {
      topic: topic,
      target_scenes: parseInt(scenesSelect.value, 10),
      voice: voiceSelect.value,
      resolution: "1080p",
      style: "Dark Modern",
    };

    const res = await fetch("/api/v1/generate-course-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to enqueue task");
    }

    const taskResp = await res.json();
    currentTaskId = taskResp.task_id;
    taskMetaLabel.textContent = `Task ID: ${currentTaskId}`;
    appendLog(`Enqueued task ${currentTaskId}. Initiating stream...`, "DISPATCH");

    const protocol = protocolSelect.value;
    if (protocol === "ws") {
      connectWebSocket(taskResp.ws_url);
    } else {
      connectSSE(taskResp.sse_url);
    }

  } catch (err) {
    appendLog(`Job dispatch error: ${err.message}`, "ERROR", true);
    cleanupStream();
  }
});
