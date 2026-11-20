"use strict";
const $ = (id) => document.getElementById(id);
const stageNames = [
  "01-denoise",
  "02-dereverb",
  "03-breaths",
  "04-mouth",
  "05-finish",
  "cleaned",
];
const stageText = [
  "Reducing background noise",
  "Reducing room echo",
  "Cleaning breaths between phrases",
  "Repairing mouth noises and clicks",
  "Adding a gentle finish",
  "Preparing your downloads",
];
let session,
  file,
  job,
  timer,
  objectUrl,
  waveContext,
  waveGeneration = 0,
  activeAudio = $("cleaned"),
  lastState,
  loading = false;
const show = (id, visible = true) => {
  $(id).hidden = !visible;
};
const formatTime = (value) => {
  const seconds = Math.max(0, Math.floor(value || 0));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
};
const fail = (message) => {
  $("error").textContent = message;
  show("error");
};
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Restore-Token": session?.token || "", ...options.headers },
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || "Restore could not complete this action.");
  return result;
}
function pause() {
  for (const id of ["original", "cleaned"]) $(id).pause();
  $("play").textContent = "▶ Play";
  $("play").setAttribute("aria-label", "Play recording");
}
function reset() {
  clearTimeout(timer);
  job = null;
  lastState = null;
  pause();
  waveGeneration++;
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = null;
  for (const id of ["original", "cleaned"]) {
    $(id).removeAttribute("src");
    $(id).load();
  }
  for (const id of [
    "error",
    "player",
    "progress",
    "cancel",
    "resume",
    "downloads",
    "new-file",
  ])
    show(id, false);
  $("clean").disabled = Boolean(session?.issues.length);
  show("clean");
  show("replace");
  $("display-label").textContent = "RECORDING LOADED";
  $("clock").textContent = "00:00";
  $("message").textContent = "Ready to clean.";
  $("file-detail").textContent = "Ready for the fixed cleanup workflow";
  $("wave").getContext("2d").clearRect(0, 0, 720, 104);
  show("wave-empty");
  localStorage.removeItem("restore-job");
}
async function choose(candidate) {
  if (!candidate) return;
  if (loading) return fail("Wait for the file transfer to finish, then drop again.");
  if (!/\.(wav|mp3|flac|m4a|ogg|aiff?)$/i.test(candidate.name))
    return fail("Please choose a supported audio file.");
  if (!candidate.size || candidate.size > 512 * 1024 * 1024)
    return fail("Choose a nonempty audio file under 512 MB.");
  if (file || job) {
    const dialog = $("replace-dialog");
    if (dialog.open) return;
    const busy = ["starting", "running", "uploading"].includes(lastState?.status);
    const question = busy
      ? "Stop the current cleanup and open " + candidate.name + "? Completed stages are saved for Resume."
      : "Replace the current recording with " + candidate.name + "? Saved recordings stay in Recent.";
    $("replace-question").textContent = question;
    $("confirm-replace").textContent = busy ? "Stop and replace" : "Replace recording";
    dialog.returnValue = "keep";
    const answer = new Promise((resolve) =>
      dialog.addEventListener("close", () => resolve(dialog.returnValue), { once: true }));
    dialog.showModal();
    if (await answer !== "replace") return;
    if (busy) {
      loading = true;
      try {
        await api(`/api/jobs/${job}/cancel`, { method: "POST" });
        await loadSession(false);
      } catch (error) {
        return fail(error.message);
      } finally {
        loading = false;
      }
    }
  }
  reset();
  for (const id of ["browse", "open-menu", "file-input"]) $(id).disabled = false;
  file = candidate;
  show("drop-zone", false);
  show("work");
  $("filename").textContent = file.name;
  $("file-detail").textContent =
    `${(file.size / 1024 / 1024).toFixed(1)} MB · ready to clean`;
  objectUrl = URL.createObjectURL(file);
  $("original").src = objectUrl;
  if (file.size < 80 * 1024 * 1024) drawWave(file);
}
async function drawWave(blob) {
  const generation = ++waveGeneration;
  try {
    waveContext ??= new (window.AudioContext || window.webkitAudioContext)();
    const decoded = await waveContext.decodeAudioData(await blob.arrayBuffer());
    if (generation !== waveGeneration) return;
    const samples = decoded.getChannelData(0),
      ctx = $("wave").getContext("2d"),
      w = 720,
      h = 104;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#6c8b52";
    for (let x = 0; x < w; x += 3) {
      const start = Math.floor((x / w) * samples.length),
        end = Math.floor(((x + 3) / w) * samples.length);
      let peak = 0;
      for (
        let n = start;
        n < end;
        n += Math.max(1, Math.floor((end - start) / 100))
      )
        peak = Math.max(peak, Math.abs(samples[n]));
      const height = Math.max(1, Math.min(h - 12, peak * (h - 12)));
      ctx.fillRect(x, Math.round((h - height) / 2), 2, Math.ceil(height));
    }
    $("clock").textContent = formatTime(decoded.duration);
    show("wave-empty", false);
  } catch {
    /* Waveform is optional; server decoding is authoritative. */
  }
}
function pickAudio(cleaned) {
  const previous = activeAudio,
    next = $(cleaned ? "cleaned" : "original");
  if (next === previous) return;
  const time = previous.currentTime || 0,
    playing = !previous.paused;
  pause();
  activeAudio = next;
  const align = () => {
    next.currentTime = Math.min(
      time,
      Math.max(0, (next.duration || time) - 0.001),
    );
    if (playing) play();
  };
  if (next.readyState >= 1) align();
  else next.addEventListener("loadedmetadata", align, { once: true });
  $("before").setAttribute("aria-pressed", String(!cleaned));
  $("after").setAttribute("aria-pressed", String(cleaned));
  $("display-label").textContent = cleaned
    ? "CLEANED VOCAL"
    : "ORIGINAL RECORDING";
  drawAudioWave(next);
}
async function drawAudioWave(audio) {
  const url = audio.getAttribute("src");
  if (
    !url ||
    !lastState?.frames ||
    lastState.frames * lastState.channels * 4 >= 80 * 1024 * 1024
  )
    return;
  try {
    const blob = await (await fetch(url)).blob();
    if (activeAudio === audio && audio.getAttribute("src") === url)
      await drawWave(blob);
  } catch {
    /* Playback remains available without a waveform. */
  }
}
async function play() {
  try {
    await activeAudio.play();
    $("play").textContent = "Ⅱ Pause";
    $("play").setAttribute("aria-label", "Pause recording");
  } catch {
    fail("Playback could not start. Try again once the audio has loaded.");
  }
}
function render(state) {
  lastState = state;
  show("drop-zone", false);
  show("work");
  $("filename").textContent = state.name;
  const busy = ["starting", "running", "uploading"].includes(state.status),
    complete = state.status === "complete";
  for (const id of ["browse", "open-menu", "file-input"]) $(id).disabled = busy;
  show("replace", false);
  show("clean", false);
  show("cancel", busy);
  show("progress");
  show("downloads", complete);
  show("new-file", !busy);
  show("resume", ["failed", "cancelled", "interrupted"].includes(state.status));
  const index = stageNames.indexOf(state.current_stage);
  document.querySelectorAll(".stages li").forEach((li, i) => {
    li.className =
      i < state.stages_complete ? "done" : busy && i === index ? "current" : "";
    if (busy && i === index) li.setAttribute("aria-current", "step");
    else li.removeAttribute("aria-current");
  });
  $("message").textContent = busy
    ? (stageText[index] || "Preparing your recording") +
      "… " +
      formatTime(state.elapsed_seconds) +
      " elapsed."
    : state.message;
  $("status").textContent = busy
    ? "Cleaning · keep Restore running"
    : complete
      ? "Your vocal is ready"
      : state.status === "cancelled"
        ? "Stopped"
        : "Ready";
  $("display-label").textContent = busy
    ? "PROCESSING LOCALLY"
    : complete
      ? "CLEANED VOCAL"
      : state.status.toUpperCase();
  if (state.duration_seconds)
    $("clock").textContent = formatTime(state.duration_seconds);
  $("file-detail").textContent = state.rate
    ? `${(state.rate / 1000).toFixed(1)} kHz · ${state.channels === 1 ? "mono" : "stereo"} · ${formatTime(state.duration_seconds)}`
    : "Preparing recording";
  if (complete) {
    const prefix = `/media/${state.id}`;
    if ($("cleaned").getAttribute("src") !== `${prefix}/cleaned/wav`) {
      pause();
      $("original").src = `${prefix}/original/wav`;
      $("cleaned").src = `${prefix}/cleaned/wav`;
      activeAudio = $("cleaned");
      $("before").setAttribute("aria-pressed", "false");
      $("after").setAttribute("aria-pressed", "true");
      drawAudioWave(activeAudio);
    }
    $("wav-download").href = `${prefix}/cleaned/wav?download=1`;
    $("mp3-download").href = `${prefix}/cleaned/mp3?download=1`;
    show("player");
    $("message").textContent =
      `Finished in ${formatTime(state.elapsed_seconds)} · 24-bit WAV + 320 kbps MP3. Compare, then save your take.`;
  }
}
async function poll() {
  if (!job) return;
  const target = job;
  try {
    const state = await api(`/api/jobs/${target}`);
    if (job !== target) return;
    show("error", false);
    render(state);
    if (["starting", "running", "uploading"].includes(state.status))
      timer = setTimeout(poll, 1800);
    else await loadSession(false);
  } catch (error) {
    if (job !== target) return;
    fail(
      "Connection interrupted. Keep Restore open; reconnecting in a moment.",
    );
    timer = setTimeout(poll, 4000);
  }
}
async function openJob(id) {
  reset();
  file = null;
  job = id;
  localStorage.setItem("restore-job", id);
  await poll();
}
async function loadSession(recover = true) {
  session = await api("/api/session");
  $("status").textContent = "Ready · files stay on this computer";
  $("profile").textContent = session.profile.toUpperCase();
  $("setup-list").replaceChildren(
    ...session.issues.map((issue) => {
      const li = document.createElement("li");
      li.textContent = issue;
      return li;
    }),
  );
  show("setup", session.issues.length > 0);
  $("clean").disabled = Boolean(session.issues.length);
  $("recent").replaceChildren(
    ...session.recent.map((item) => {
      const li = document.createElement("li"),
        button = document.createElement("button"),
        span = document.createElement("span");
      button.textContent = item.name;
      button.disabled = Boolean(session.active && session.active !== item.id);
      button.addEventListener("click", () => {
        if (window.restoreDesktop) $("recent-wrap").open = false;
        openJob(item.id);
      });
      span.textContent = item.status;
      li.append(button, span);
      return li;
    }),
  );
  show("recent-wrap", session.recent.length > 0);
  $("recent-count").textContent = `(${session.recent.length})`;
  if (recover) {
    const stored = localStorage.getItem("restore-job");
    const found =
      session.active || session.recent.find((item) => item.id === stored)?.id;
    if (found) await openJob(found);
  }
}
for (const id of ["browse", "replace", "open-menu", "new-file"])
  $(id).addEventListener("click", () => {
    if (
      !loading &&
      !["starting", "running", "uploading"].includes(lastState?.status)
    )
      $("file-input").click();
  });
$("file-input").addEventListener("change", (e) => {
  choose(e.target.files[0]);
  e.target.value = "";
});
for (const name of ["dragenter", "dragover"])
  $("drop-zone").addEventListener(name, (e) => {
    e.preventDefault();
    $("drop-zone").classList.add("dragging");
  });
for (const name of ["dragleave", "drop"])
  $("drop-zone").addEventListener(name, (e) => {
    e.preventDefault();
    $("drop-zone").classList.remove("dragging");
  });
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer.files.length > 1) return fail("Drop one recording at a time.");
  choose(e.dataTransfer.files[0]);
});
if (window.restoreDesktop && window.chrome?.webview) {
  document.documentElement.classList.add("native");
  show("window-controls");
  const recent = $("recent-wrap");
  $("help-menu").before(recent);
  document.addEventListener("click", (e) => {
    if (recent.open && !recent.contains(e.target)) recent.open = false;
  });
  recent.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      recent.open = false;
      recent.querySelector("summary").focus();
    }
  });
  for (const command of ["minimize", "maximize", "close"])
    $(command).addEventListener("click", () => window.chrome.webview.postMessage(command));
  for (const ext of ["wav", "mp3"]) {
    const button = $(ext + "-download");
    button.title = "Click to save or drag the cleaned file into another app";
    button.addEventListener("click", (e) => {
      e.preventDefault();
      if (lastState?.status === "complete")
        window.chrome.webview.postMessage("save " + job + " " + ext);
    });
    button.addEventListener("dragstart", (e) => {
      e.preventDefault();
      if (lastState?.status === "complete")
        window.chrome.webview.postMessage("drag " + job + " " + ext);
    });
  }
}
$("clean").addEventListener("click", async () => {
  if (!file || loading) return;
  loading = true;
  show("error", false);
  $("clean").disabled = true;
  $("clean").textContent = "Opening recording…";
  try {
    const result = await api(
      `/api/jobs?name=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        body: file,
        headers: { "Content-Type": "application/octet-stream" },
      },
    );
    job = result.id;
    localStorage.setItem("restore-job", job);
    await poll();
  } catch (error) {
    fail(error.message);
    $("clean").disabled = false;
  } finally {
    loading = false;
    $("clean").textContent = "✦ Clean vocal";
  }
});
$("cancel").addEventListener("click", async () => {
  try {
    $("cancel").disabled = true;
    await api(`/api/jobs/${job}/cancel`, { method: "POST" });
    clearTimeout(timer);
    await poll();
  } catch (e) {
    fail(e.message);
  } finally {
    $("cancel").disabled = false;
  }
});
$("resume").addEventListener("click", async () => {
  try {
    $("resume").disabled = true;
    await api(`/api/jobs/${job}/resume`, { method: "POST" });
    clearTimeout(timer);
    await poll();
  } catch (e) {
    fail(e.message);
  } finally {
    $("resume").disabled = false;
  }
});
$("before").addEventListener("click", () => pickAudio(false));
$("after").addEventListener("click", () => pickAudio(true));
$("play").addEventListener("click", () =>
  activeAudio.paused ? play() : pause(),
);
$("seek").addEventListener("input", () => {
  if (Number.isFinite(activeAudio.duration))
    activeAudio.currentTime =
      (Number($("seek").value) / 1000) * activeAudio.duration;
});
for (const id of ["original", "cleaned"]) {
  $(id).addEventListener("timeupdate", () => {
    if ($(id) !== activeAudio) return;
    $("play-time").textContent =
      `${formatTime(activeAudio.currentTime)} / ${formatTime(activeAudio.duration)}`;
    $("seek").value = activeAudio.duration
      ? (activeAudio.currentTime / activeAudio.duration) * 1000
      : 0;
  });
  $(id).addEventListener("ended", pause);
  $(id).addEventListener("loadedmetadata", () => {
    if ($(id) === activeAudio)
      $("play-time").textContent = `0:00 / ${formatTime(activeAudio.duration)}`;
  });
}
for (const id of ["help-button", "help-menu"])
  $(id).addEventListener("click", () => $("about").showModal());
for (const id of ["close-help", "help-done"])
  $(id).addEventListener("click", () => $("about").close());
loadSession().catch(() => {
  fail(
    "Restore could not connect. Start the local app, then reload this page.",
  );
  $("status").textContent = "Offline";
});
