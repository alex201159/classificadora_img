"use strict";

const state = {
  config: null,
  classes: [],
  selectedClassId: null,
  stream: null,
  toastTimer: null,
};

const elements = {
  tabs: document.querySelectorAll(".tab"),
  views: document.querySelectorAll(".view"),
  machineName: document.querySelector("#machine-name"),
  modeBadge: document.querySelector("#mode-badge"),
  machineBadge: document.querySelector("#machine-badge"),
  clock: document.querySelector("#clock"),
  cameraState: document.querySelector("#camera-state"),
  safetyState: document.querySelector("#safety-state"),
  currentClass: document.querySelector("#current-class"),
  totalCount: document.querySelector("#total-count"),
  startMachine: document.querySelector("#start-machine"),
  stopMachine: document.querySelector("#stop-machine"),
  operationVideo: document.querySelector("#operation-video"),
  registrationVideo: document.querySelector("#registration-video"),
  enableCamera: document.querySelector("#enable-camera"),
  captureImage: document.querySelector("#capture-image"),
  chooseImage: document.querySelector("#choose-image"),
  imageFile: document.querySelector("#image-file"),
  captureCanvas: document.querySelector("#capture-canvas"),
  selectedClassLabel: document.querySelector("#selected-class-label"),
  classCount: document.querySelector("#class-count"),
  classForm: document.querySelector("#class-form"),
  className: document.querySelector("#class-name"),
  classColor: document.querySelector("#class-color"),
  classShape: document.querySelector("#class-shape"),
  classOutput: document.querySelector("#class-output"),
  classList: document.querySelector("#class-list"),
  settingMachine: document.querySelector("#setting-machine"),
  settingCamera: document.querySelector("#setting-camera"),
  settingOutputs: document.querySelector("#setting-outputs"),
  toast: document.querySelector("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Falha de comunicação");
  }
  return payload;
}

function showToast(message, error = false) {
  clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.classList.add("visible");
  state.toastTimer = setTimeout(() => elements.toast.classList.remove("visible"), 2800);
}

function selectView(viewId) {
  const targetExists = Array.from(elements.views).some((view) => view.id === viewId);
  if (!targetExists) {
    return;
  }
  elements.tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.view === viewId));
  elements.views.forEach((view) => view.classList.toggle("active", view.id === viewId));
  if (window.location.hash !== `#${viewId}`) {
    window.history.replaceState(null, "", `#${viewId}`);
  }
}

async function loadConfig() {
  state.config = await api("/api/config");
  elements.machineName.textContent = state.config.machine_name;
  elements.modeBadge.textContent = state.config.simulation ? "SIMULAÇÃO" : "PRODUÇÃO";
  elements.settingMachine.textContent = state.config.machine_name;
  elements.settingCamera.textContent = `DISPOSITIVO ${state.config.camera_device}`;
  elements.settingOutputs.textContent = state.config.outputs.join(", ").toUpperCase();
  elements.classOutput.replaceChildren();
  state.config.outputs.forEach((output) => {
    const option = document.createElement("option");
    option.value = output;
    option.textContent = output.replaceAll("_", " ").toUpperCase();
    elements.classOutput.append(option);
  });
}

async function refreshStatus() {
  try {
    const status = await api("/api/status");
    elements.machineBadge.textContent = status.running ? "EM OPERAÇÃO" : "PARADO";
    elements.machineBadge.classList.toggle("running", status.running);
    elements.machineBadge.classList.toggle("neutral", !status.running);
    elements.safetyState.textContent = status.safe_state ? "SEGURA" : "PRODUÇÃO";
    elements.safetyState.classList.toggle("safe", status.safe_state);
    elements.totalCount.textContent = status.total_caps;
    elements.startMachine.disabled = status.running;
    elements.stopMachine.disabled = !status.running;
  } catch (error) {
    elements.machineBadge.textContent = "SEM CONEXÃO";
    elements.machineBadge.classList.remove("running");
    elements.machineBadge.classList.add("neutral");
  }
}

async function machineCommand(command) {
  try {
    await api(`/api/machine/${command}`, { method: "POST", body: "{}" });
    await refreshStatus();
    showToast(command === "start" ? "Operação iniciada em simulação" : "Máquina parada em segurança");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function enableCamera() {
  if (state.stream) {
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    showToast("A câmera não está disponível neste navegador", true);
    return;
  }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    elements.operationVideo.srcObject = state.stream;
    elements.registrationVideo.srcObject = state.stream;
    document.querySelectorAll(".camera-frame").forEach((frame) => frame.classList.add("has-video"));
    elements.cameraState.textContent = "AO VIVO";
    elements.cameraState.classList.add("safe");
    elements.enableCamera.textContent = "CÂMERA ATIVA";
    elements.enableCamera.disabled = true;
  } catch (error) {
    showToast("Não foi possível acessar a câmera. Use ARQUIVO para cadastrar.", true);
  }
}

function selectedClass() {
  return state.classes.find((capClass) => capClass.id === state.selectedClassId) || null;
}

async function loadClasses(preferredId = null) {
  const payload = await api("/api/classes");
  state.classes = payload.classes;
  if (preferredId && state.classes.some((item) => item.id === preferredId)) {
    state.selectedClassId = preferredId;
  } else if (!selectedClass() && state.classes.length > 0) {
    state.selectedClassId = state.classes[0].id;
  }
  renderClasses();
}

function renderClasses() {
  elements.classList.replaceChildren();
  elements.classCount.textContent = `${state.classes.length} ${state.classes.length === 1 ? "CADASTRO" : "CADASTROS"}`;
  const active = selectedClass();
  elements.selectedClassLabel.textContent = active ? active.name.toUpperCase() : "NENHUMA CLASSE";
  elements.currentClass.textContent = active ? active.name.toUpperCase() : "NÃO SELECIONADA";

  if (state.classes.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-list";
    empty.textContent = "Nenhuma tampa cadastrada";
    elements.classList.append(empty);
    return;
  }

  state.classes.forEach((capClass) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "class-item";
    button.classList.toggle("selected", capClass.id === state.selectedClassId);
    button.title = `Selecionar ${capClass.name}`;
    button.addEventListener("click", () => {
      state.selectedClassId = capClass.id;
      renderClasses();
    });

    const thumb = document.createElement("div");
    thumb.className = "class-thumb";
    if (capClass.samples.length > 0) {
      const image = document.createElement("img");
      image.src = capClass.samples.at(-1).url;
      image.alt = "";
      thumb.append(image);
    } else {
      thumb.textContent = capClass.name.slice(0, 1).toUpperCase();
    }

    const meta = document.createElement("div");
    meta.className = "class-meta";
    const name = document.createElement("strong");
    name.textContent = capClass.name;
    const details = document.createElement("span");
    details.textContent = `${capClass.samples.length} imagens · ${capClass.output.replaceAll("_", " ")}`;
    meta.append(name, details);
    button.append(thumb, meta);
    elements.classList.append(button);
  });
}

async function createClass(event) {
  event.preventDefault();
  try {
    const created = await api("/api/classes", {
      method: "POST",
      body: JSON.stringify({
        name: elements.className.value,
        color: elements.classColor.value,
        shape: elements.classShape.value,
        output: elements.classOutput.value,
      }),
    });
    elements.classForm.reset();
    await loadClasses(created.id);
    showToast("Tipo cadastrado. Capture as imagens da tampa.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function captureImage() {
  const capClass = selectedClass();
  if (!capClass) {
    showToast("Cadastre ou selecione um tipo de tampa", true);
    return;
  }
  if (!state.stream || elements.registrationVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    showToast("Ative a câmera ou escolha um arquivo", true);
    return;
  }

  const video = elements.registrationVideo;
  const canvas = elements.captureCanvas;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  await saveImage(canvas.toDataURL("image/jpeg", 0.9));
}

async function saveImage(dataUrl) {
  const capClass = selectedClass();
  if (!capClass) {
    showToast("Selecione um tipo de tampa", true);
    return;
  }
  try {
    await api(`/api/classes/${encodeURIComponent(capClass.id)}/samples`, {
      method: "POST",
      body: JSON.stringify({ image: dataUrl }),
    });
    await loadClasses(capClass.id);
    showToast("Imagem cadastrada com sucesso");
  } catch (error) {
    showToast(error.message, true);
  }
}

function handleFile(event) {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) {
    return;
  }
  if (!selectedClass()) {
    showToast("Cadastre ou selecione um tipo de tampa", true);
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => saveImage(reader.result));
  reader.addEventListener("error", () => showToast("Não foi possível ler a imagem", true));
  reader.readAsDataURL(file);
}

function updateClock() {
  elements.clock.textContent = new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function bindEvents() {
  elements.tabs.forEach((tab) => tab.addEventListener("click", () => selectView(tab.dataset.view)));
  elements.startMachine.addEventListener("click", () => machineCommand("start"));
  elements.stopMachine.addEventListener("click", () => machineCommand("stop"));
  elements.enableCamera.addEventListener("click", enableCamera);
  elements.captureImage.addEventListener("click", captureImage);
  elements.chooseImage.addEventListener("click", () => elements.imageFile.click());
  elements.imageFile.addEventListener("change", handleFile);
  elements.classForm.addEventListener("submit", createClass);
  window.addEventListener("beforeunload", () => state.stream?.getTracks().forEach((track) => track.stop()));
}

async function initialize() {
  bindEvents();
  selectView(window.location.hash.slice(1) || "operation");
  updateClock();
  setInterval(updateClock, 1000);
  try {
    await Promise.all([loadConfig(), loadClasses(), refreshStatus()]);
    setInterval(refreshStatus, 1000);
  } catch (error) {
    showToast(error.message, true);
  }
}

initialize();
