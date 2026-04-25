const CAMERA_KEYS = ["head", "left_wrist", "right_wrist"];
const PRESET_TASKS = [
  "pick up foam ball",
  "add held object to skewer",
  "drop held object in cup",
];
const STATUS_PILL_VARIANTS = {
  ready: "success",
  degraded: "danger",
  reconnecting: "warning",
  reloading_model: "warning",
  stopped: "danger",
  starting: "neutral",
};

const state = {
  status: null,
  apiBaseUrl: detectDefaultApiBaseUrl(),
  observationIntervalMs: 500,
  observationTimer: null,
  statusTimer: null,
  statusEndpointAvailable: true,
  observationInFlight: false,
  statusInFlight: false,
  connectionHealthy: false,
  lastPollError: "",
};

document.addEventListener("DOMContentLoaded", () => {
  const elements = getElements();
  initializeApiBaseUrl(elements);
  renderPresetButtons(elements);
  bindEvents(elements);
  restartObservationPolling(elements);
  state.statusTimer = window.setInterval(() => {
    void fetchStatus(elements);
  }, 2000);

  logEvent(elements, "Dashboard loaded", "info");
  void Promise.all([fetchStatus(elements), fetchObservation(elements)]);
});

function getElements() {
  const cameraElements = Object.fromEntries(
    CAMERA_KEYS.map((cameraKey) => {
      const card = document.querySelector(`[data-camera="${cameraKey}"]`);
      return [
        cameraKey,
        {
          card,
          image: card.querySelector('[data-role="image"]'),
          placeholder: card.querySelector('[data-role="placeholder"]'),
          timestamp: card.querySelector('[data-role="timestamp"]'),
        },
      ];
    })
  );

  return {
    connectionPill: document.getElementById("connection-pill"),
    runtimePill: document.getElementById("runtime-pill"),
    observationPill: document.getElementById("observation-pill"),
    observationInterval: document.getElementById("observation-interval"),
    apiBaseUrlInput: document.getElementById("api-base-url"),
    applyApiBase: document.getElementById("apply-api-base"),
    refreshNow: document.getElementById("refresh-now"),
    cameraStatus: document.getElementById("camera-status"),
    taskInput: document.getElementById("task-input"),
    sendTask: document.getElementById("send-task"),
    syncCurrentTask: document.getElementById("sync-current-task"),
    presetButtons: document.getElementById("preset-buttons"),
    toggleAct: document.getElementById("toggle-act"),
    baseStep: document.getElementById("base-step"),
    baseLeft: document.getElementById("base-left"),
    baseRight: document.getElementById("base-right"),
    reconnectRuntime: document.getElementById("reconnect-runtime"),
    checkpointPath: document.getElementById("checkpoint-path"),
    policyType: document.getElementById("policy-type"),
    reloadModel: document.getElementById("reload-model"),
    motorGrid: document.getElementById("motor-grid"),
    eventLog: document.getElementById("event-log"),
    statusFields: {
      state: document.getElementById("status-state"),
      task: document.getElementById("status-task"),
      model: document.getElementById("status-model"),
      pendingModel: document.getElementById("status-pending-model"),
      baseAngle: document.getElementById("status-base-angle"),
      observationAge: document.getElementById("status-observation-age"),
      reason: document.getElementById("status-reason"),
      message: document.getElementById("status-message"),
    },
    cameras: cameraElements,
  };
}

function bindEvents(elements) {
  elements.applyApiBase.addEventListener("click", () => {
    applyApiBaseUrl(elements);
  });

  elements.apiBaseUrlInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyApiBaseUrl(elements);
    }
  });

  elements.observationInterval.addEventListener("change", () => {
    state.observationIntervalMs = Number(elements.observationInterval.value);
    restartObservationPolling(elements);
    void fetchObservation(elements);
  });

  elements.refreshNow.addEventListener("click", () => {
    void fetchObservation(elements);
    void fetchStatus(elements);
  });

  elements.sendTask.addEventListener("click", () => {
    void sendTask(elements);
  });

  elements.syncCurrentTask.addEventListener("click", () => {
    elements.taskInput.value = state.status?.current_task || "";
  });

  elements.taskInput.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void sendTask(elements);
    }
  });

  elements.toggleAct.addEventListener("click", () => {
    void toggleActions(elements);
  });

  elements.baseLeft.addEventListener("click", () => {
    void moveBase(elements, "left");
  });

  elements.baseRight.addEventListener("click", () => {
    void moveBase(elements, "right");
  });

  elements.reconnectRuntime.addEventListener("click", () => {
    void reconnectRuntime(elements);
  });

  elements.reloadModel.addEventListener("click", () => {
    void reloadModel(elements);
  });
}

function renderPresetButtons(elements) {
  PRESET_TASKS.forEach((task) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.textContent = task;
    button.addEventListener("click", () => {
      elements.taskInput.value = task;
    });
    elements.presetButtons.append(button);
  });
}

function initializeApiBaseUrl(elements) {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api")?.trim();
  const fromStorage = window.localStorage.getItem("robotDashboardApiBaseUrl")?.trim();
  const candidate =
    fromQuery || fromStorage || elements.apiBaseUrlInput.value.trim() || detectDefaultApiBaseUrl();
  state.apiBaseUrl = sanitizeApiBaseUrl(candidate);
  elements.apiBaseUrlInput.value = state.apiBaseUrl;
}

function applyApiBaseUrl(elements) {
  const candidate = elements.apiBaseUrlInput.value.trim();
  state.apiBaseUrl = sanitizeApiBaseUrl(candidate);
  elements.apiBaseUrlInput.value = state.apiBaseUrl;
  window.localStorage.setItem("robotDashboardApiBaseUrl", state.apiBaseUrl);
  state.connectionHealthy = false;
  state.lastPollError = "";
  setPill(elements.connectionPill, "Connecting", "neutral");
  logEvent(elements, `Using API base URL: ${state.apiBaseUrl}`, "info");
  void Promise.all([fetchStatus(elements), fetchObservation(elements)]);
}

function sanitizeApiBaseUrl(value) {
  return value.replace(/\/+$/, "") || detectDefaultApiBaseUrl();
}

function detectDefaultApiBaseUrl() {
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    if (window.location.pathname.startsWith("/dashboard")) {
      return window.location.origin;
    }

    const url = new URL(window.location.href);
    url.port = "8000";
    url.pathname = "";
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/+$/, "");
  }

  return "http://127.0.0.1:8000";
}

function restartObservationPolling(elements) {
  if (state.observationTimer !== null) {
    window.clearInterval(state.observationTimer);
  }

  if (state.observationIntervalMs > 0) {
    state.observationTimer = window.setInterval(() => {
      void fetchObservation(elements);
    }, state.observationIntervalMs);
    setPill(elements.observationPill, `Polling ${formatInterval(state.observationIntervalMs)}`, "neutral");
    return;
  }

  state.observationTimer = null;
  setPill(elements.observationPill, "Polling paused", "warning");
}

async function fetchStatus(elements) {
  if (!state.statusEndpointAvailable) {
    return;
  }

  if (state.statusInFlight) {
    return;
  }

  state.statusInFlight = true;
  try {
    const data = await fetchJson("/status");
    state.status = data;
    markConnectionHealthy(elements);
    updateStatus(elements, data);
  } catch (error) {
    if (isNotFoundError(error)) {
      disableStatusFeatures(elements);
      return;
    }
    handlePollError(elements, "Status poll failed", error);
  } finally {
    state.statusInFlight = false;
  }
}

async function fetchObservation(elements) {
  if (state.observationIntervalMs === 0 && state.observationTimer === null) {
    setPill(elements.observationPill, "Polling paused", "warning");
  }

  if (state.observationInFlight) {
    return;
  }

  state.observationInFlight = true;
  try {
    const data = await fetchJson("/observation");
    markConnectionHealthy(elements);
    updateObservation(elements, data);
  } catch (error) {
    handlePollError(elements, "Observation poll failed", error);
  } finally {
    state.observationInFlight = false;
  }
}

async function sendTask(elements) {
  const task = elements.taskInput.value.trim();
  if (!task) {
    logEvent(elements, "Task prompt is empty", "warning");
    return;
  }

  const response = await runMutation(
    elements,
    "Send task",
    "/task",
    { task },
    {
      successMessage: `Task updated to "${task}"`,
    }
  );

  if (response) {
    elements.taskInput.value = task;
    await fetchStatus(elements);
  }
}

async function toggleActions(elements) {
  const nextAllow = !Boolean(state.status?.take_action);
  const response = await runMutation(
    elements,
    nextAllow ? "Enable actions" : "Pause actions",
    "/allow_act",
    { allow_act: nextAllow },
    {
      successMessage: nextAllow ? "Robot actions enabled" : "Robot actions paused",
    }
  );

  if (response) {
    await fetchStatus(elements);
  }
}

async function moveBase(elements, direction) {
  const magnitude = Math.min(Math.max(Math.abs(Number(elements.baseStep.value) || 500), 1), 2000);
  const steps = direction === "left" ? magnitude : -magnitude;
  const response = await runMutation(
    elements,
    `Move base ${direction}`,
    "/base",
    { steps },
    {
      successMessage: `Base moved ${direction} by ${magnitude} steps`,
    }
  );

  if (response) {
    await fetchStatus(elements);
  }
}

async function reconnectRuntime(elements) {
  const response = await runMutation(
    elements,
    "Reconnect runtime",
    "/reconnect",
    {
      force: false,
      reason: "web_dashboard",
    },
    {
      successMessage: "Reconnect requested",
    }
  );

  if (response) {
    await fetchStatus(elements);
  }
}

async function reloadModel(elements) {
  const checkpointPath = elements.checkpointPath.value.trim();
  if (!checkpointPath) {
    logEvent(elements, "Checkpoint path is required for model reload", "warning");
    return;
  }

  const policyType = elements.policyType.value.trim();
  const response = await runMutation(
    elements,
    "Reload model",
    "/reload_model",
    {
      checkpoint_path: checkpointPath,
      policy_type: policyType || null,
    },
    {
      successMessage: `Model reload requested for ${checkpointPath}`,
    }
  );

  if (response) {
    await fetchStatus(elements);
  }
}

async function runMutation(elements, label, path, body, { successMessage }) {
  try {
    const data = await fetchJson(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    logEvent(elements, successMessage, "success");
    markConnectionHealthy(elements);
    return data;
  } catch (error) {
    logEvent(elements, `${label} failed: ${error.message}`, "error");
    setPill(elements.connectionPill, "Disconnected", "danger");
    return null;
  }
}

function updateObservation(elements, payload) {
  const metadata = payload.metadata || {};
  const nowLabel = new Date().toLocaleTimeString();
  const stale = Boolean(metadata.is_stale);
  const ageText =
    metadata.staleness_seconds == null ? "fresh" : `${formatNumber(metadata.staleness_seconds)}s old`;
  elements.cameraStatus.textContent = stale
    ? `Serving cached observation (${ageText}). ${metadata.message || ""}`.trim()
    : `Live observation received at ${nowLabel}`;

  setPill(
    elements.observationPill,
    stale ? `Frames stale (${ageText})` : `Frames live (${formatInterval(state.observationIntervalMs)})`,
    stale ? "warning" : "success"
  );

  CAMERA_KEYS.forEach((cameraKey) => {
    const camera = elements.cameras[cameraKey];
    const base64Image = payload.images_base64?.[cameraKey];
    camera.card.classList.toggle("is-stale", stale);

    if (!base64Image) {
      camera.image.classList.remove("visible");
      camera.placeholder.classList.remove("hidden");
      camera.timestamp.textContent = "No frame available";
      return;
    }

    camera.image.src = base64Image.startsWith("data:")
      ? base64Image
      : `data:image/jpeg;base64,${base64Image}`;
    camera.image.classList.add("visible");
    camera.placeholder.classList.add("hidden");
    camera.timestamp.textContent = stale ? `Cached ${ageText}` : `Updated ${nowLabel}`;
  });

  updateMotorGrid(elements, payload.motor_angles || {});

  if (payload.current_task) {
    elements.statusFields.task.textContent = payload.current_task;
    if (!elements.taskInput.value.trim()) {
      elements.taskInput.placeholder = `Current: ${payload.current_task}`;
    }
  }

  elements.statusFields.observationAge.textContent =
    metadata.staleness_seconds == null ? "fresh" : `${formatNumber(metadata.staleness_seconds)}s`;
}

function updateStatus(elements, status) {
  const variant = STATUS_PILL_VARIANTS[status.state] || "neutral";
  setPill(elements.runtimePill, status.state || "unknown", variant);

  elements.statusFields.state.textContent = status.state || "-";
  elements.statusFields.task.textContent = status.current_task || "-";
  elements.statusFields.model.textContent = status.current_model_path || "-";
  elements.statusFields.pendingModel.textContent = status.pending_model_path || "-";
  elements.statusFields.baseAngle.textContent =
    status.base_angle == null ? "-" : String(status.base_angle);
  elements.statusFields.observationAge.textContent =
    status.observation_age_seconds == null ? "fresh" : `${formatNumber(status.observation_age_seconds)}s`;
  elements.statusFields.reason.textContent = status.reason || "-";
  elements.statusFields.message.textContent = status.message || "-";

  elements.toggleAct.textContent = status.take_action ? "Pause Actions" : "Enable Actions";
  elements.toggleAct.classList.toggle("secondary-button", Boolean(status.take_action));
  elements.checkpointPath.placeholder = status.current_model_path || elements.checkpointPath.placeholder;

  const isBusy = Boolean(status.active_operation);
  const isReady = status.state === "ready";

  elements.reconnectRuntime.disabled = isBusy;
  elements.reloadModel.disabled = isBusy;
  elements.toggleAct.disabled = !isReady && !status.take_action;
  elements.baseLeft.disabled = !isReady;
  elements.baseRight.disabled = !isReady;

  if (status.active_operation) {
    logEvent(elements, `Runtime operation active: ${status.active_operation}`, "info", true);
  }
}

function updateMotorGrid(elements, motorAngles) {
  const flattened = flattenEntries(motorAngles);
  elements.motorGrid.replaceChildren();

  if (flattened.length === 0) {
    const emptyCard = document.createElement("div");
    emptyCard.className = "metric-card empty";
    emptyCard.textContent = "No motor data in the latest observation.";
    elements.motorGrid.append(emptyCard);
    return;
  }

  flattened.forEach(([name, value]) => {
    const card = document.createElement("div");
    card.className = "metric-card";

    const title = document.createElement("strong");
    title.textContent = name;

    const reading = document.createElement("span");
    reading.textContent = formatValue(value);

    card.append(title, reading);
    elements.motorGrid.append(card);
  });
}

function flattenEntries(value, prefix = "") {
  if (Array.isArray(value)) {
    return value.flatMap((entry, index) => flattenEntries(entry, `${prefix}_${index}`));
  }

  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([key, entry]) =>
      flattenEntries(entry, prefix ? `${prefix}.${key}` : key)
    );
  }

  return [[prefix, value]];
}

function formatValue(value) {
  if (typeof value === "number") {
    return formatNumber(value);
  }
  return String(value);
}

function formatNumber(value) {
  return Number(value).toFixed(3).replace(/\.?0+$/, "");
}

function formatInterval(intervalMs) {
  if (!intervalMs) {
    return "paused";
  }
  if (intervalMs < 1000) {
    return `${intervalMs}ms`;
  }
  return `${formatNumber(intervalMs / 1000)}s`;
}

function setPill(element, label, variant) {
  element.textContent = label;
  element.className = "pill";
  element.classList.add(`pill-${variant}`);
}

function markConnectionHealthy(elements) {
  if (!state.connectionHealthy) {
    logEvent(elements, "Connected to robot runtime", "success");
  }

  state.connectionHealthy = true;
  state.lastPollError = "";
  setPill(elements.connectionPill, "Connected", "success");
}

function disableStatusFeatures(elements) {
  if (!state.statusEndpointAvailable) {
    return;
  }

  state.statusEndpointAvailable = false;
  if (state.statusTimer !== null) {
    window.clearInterval(state.statusTimer);
    state.statusTimer = null;
  }

  setPill(elements.runtimePill, "legacy backend", "neutral");
  elements.statusFields.state.textContent = "legacy backend";
  elements.statusFields.reason.textContent = "status endpoint unavailable";
  elements.statusFields.message.textContent = "Using /observation only";
  elements.reconnectRuntime.disabled = true;
  elements.reloadModel.disabled = true;
  logEvent(elements, "Backend has no /status (legacy mode). Live camera/controls continue via existing APIs.", "warning");
}

function handlePollError(elements, prefix, error) {
  const message = `${prefix}: ${error.message}`;
  if (state.lastPollError !== message) {
    logEvent(elements, message, "error");
    state.lastPollError = message;
  }

  state.connectionHealthy = false;
  setPill(elements.connectionPill, "Disconnected", "danger");
  elements.cameraStatus.textContent = message;
}

function logEvent(elements, message, level = "info", dedupe = false) {
  const existingFirst = elements.eventLog.firstElementChild?.dataset.message;
  if (dedupe && existingFirst === message) {
    return;
  }

  const item = document.createElement("li");
  item.dataset.message = message;

  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString();

  const text = document.createElement("span");
  text.className = level;
  text.textContent = message;

  item.append(time, text);
  elements.eventLog.prepend(item);

  while (elements.eventLog.children.length > 10) {
    elements.eventLog.removeChild(elements.eventLog.lastElementChild);
  }
}

async function fetchJson(path, options = {}) {
  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  const raw = await response.text();
  let payload = null;

  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch (error) {
      payload = raw;
    }
  }

  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && (payload.detail || payload.message)) ||
      response.statusText ||
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

function isNotFoundError(error) {
  return typeof error?.message === "string" && error.message.toLowerCase().includes("not found");
}

function buildApiUrl(path) {
  return `${state.apiBaseUrl}${path}`;
}
