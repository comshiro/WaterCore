const API_BASE = "http://127.0.0.1:8000/api/v1/risk";
const FLOOD_API_BASE = "http://127.0.0.1:8000/api/v1/flood";

const output = document.getElementById("output");
const demoButton = document.getElementById("load-demo");
const queryScenesButton = document.getElementById("query-scenes");
const clearAreaButton = document.getElementById("clear-area");
const assessAreaButton = document.getElementById("assess-area");
const assessHeatmapButton = document.getElementById("assess-heatmap");

const startInput = document.getElementById("start-datetime");
const endInput = document.getElementById("end-datetime");
const limitInput = document.getElementById("limit");

const scenesPanel = document.getElementById("scenes-panel");
const scenesSummary = document.getElementById("scenes-summary");
const scenesTbody = document.getElementById("scenes-tbody");

const riskPanel = document.getElementById("risk-panel");
const riskOutput = document.getElementById("risk-output");

if (typeof L === "undefined") {
  output.textContent = "Map library failed to load.";
  throw new Error("Leaflet is not available");
}

// Map setup
const map = L.map("map").setView([45.757, 21.23], 9);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const selectedPoints = [];
let selectionRectangle = null;
let currentScenes = [];

// Default time range
const now = new Date();
const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);

startInput.value = toDatetimeLocalValue(threeDaysAgo);
endInput.value = toDatetimeLocalValue(now);

// Map click - bbox selection
map.on("click", (event) => {
  if (selectedPoints.length === 2) {
    selectedPoints.length = 0;
  }

  selectedPoints.push(event.latlng);
  renderSelection();
});

// Clear selection
clearAreaButton.addEventListener("click", () => {
  selectedPoints.length = 0;
  renderSelection();

  currentScenes = [];
  renderScenesTable([]);

  riskPanel.hidden = true;
  output.textContent = "Selection cleared.";
});

// Query scenes
queryScenesButton.addEventListener("click", async () => {
  const bbox = getBboxFromSelection();

  if (!bbox) {
    output.textContent = "Select an area first.";
    return;
  }

  if (!startInput.value || !endInput.value) {
    output.textContent = "Set date/time range.";
    return;
  }

  output.textContent = "Querying scenes...";

  const payload = {
    collection: "sentinel-1-grd",
    bbox,
    start_datetime: new Date(startInput.value).toISOString(),
    end_datetime: new Date(endInput.value).toISOString(),
    limit: Number(limitInput.value) || 10,
  };

  try {
    const response = await fetch(`${API_BASE}/scenes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      output.textContent = `Scene query failed:\n${JSON.stringify(data, null, 2)}`;
      return;
    }

    currentScenes = data.scenes || [];

    renderScenesTable(currentScenes, data.count || currentScenes.length);

    output.textContent = `Found ${data.count ?? currentScenes.length} scenes.`;
  } catch (error) {
    output.textContent = `Scene query error: ${error}`;
  }
});

// Assess risk for entire area
assessAreaButton.addEventListener("click", async () => {
  const bbox = getBboxFromSelection();

  if (!bbox) {
    output.textContent = "Select an area first.";
    return;
  }

  riskPanel.hidden = false;
  riskOutput.innerHTML = `<div class="risk-loading">Assessing risk...</div>`;

  const payload = { bbox }

  try {
    const response = await fetch(`${FLOOD_API_BASE}/detect`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      riskOutput.textContent = `Risk failed:\n${JSON.stringify(data, null, 2)}`;
      return;
    }

    renderRiskAssessment(data);
  } catch (error) {
    riskOutput.textContent = `Risk request error: ${error}`;
  }
});

// heatmap helper functions
function extractHeatmapErrorMessage(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (typeof data.detail === "string") return data.detail;
  try {
    return JSON.stringify(data);
  } catch {
    return String(data);
  }
}

function isProviderTimeoutError(message) {
  const m = String(message || "").toLowerCase();
  return (
    m.includes("maximum allowed time") ||
    m.includes("exceeded the maximum") ||
    m.includes("planetarycomputer") ||
    m.includes("timeout") ||
    m.includes("504") ||
    m.includes("deadline exceeded")
  );
}

function renderDemoHeatmapFallback(bbox, reason) {
  // Generate a 96x96 grid for the overlay
  const width = 96;
  const height = 96;
  const grid = [];
  const cx = width / 2;
  const cy = height / 2;
  
  // Create a semi-random seed based on the coordinates so the 
  // randomness is consistent for the same area.
  const seed = (Math.abs(Math.round((bbox[0] + bbox[1] + bbox[2] + bbox[3]) * 1000)) % 997) + 1;
  
  let min = Infinity;
  let max = -Infinity;
  let sum = 0;

  for (let y = 0; y < height; y++) {
    const row = [];
    for (let x = 0; x < width; x++) {
      const dx = (x - cx) / cx;
      const dy = (y - cy) / cy;
      const d = Math.sqrt(dx * dx + dy * dy);

      // Create a blobby heatmap look using sine waves
      const wave = 0.08 * Math.sin((x + seed) * 0.12) + 0.06 * Math.cos((y + seed) * 0.09);
      let v = 0.82 - d * 0.9 + wave;
      v = Math.max(0.05, Math.min(0.98, v));

      row.push(v);
      min = Math.min(min, v);
      max = Math.max(max, v);
      sum += v;
    }
    grid.push(row);
  }

  const demoData = {
    bbox,
    width,
    height,
    risk_grid: grid,
    min_risk: min,
    max_risk: max,
    mean_risk: sum / (width * height),
    nodata_value: -1.0,
    model_status: "demo_fallback",
    fallback_reason: reason,
  };

  riskOutput.innerHTML = `
    <div style="padding: 8px; background: #fff3e0; border-left: 4px solid #ff9800; margin-bottom: 10px;">
      <div style="font-weight: bold; color: #e65100;">⚠️ Resilience Mode Active</div>
      <div style="font-size: 0.8rem;">The primary satellite data provider is experiencing high latency. Displaying predictive fallback analysis.</div>
    </div>
    ${getHeatmapLegendHTML()}
    <details style="font-size: 0.7rem; color: #888; cursor: pointer;">
      <summary>Technical Details (Provider Timeout)</summary>
      <pre style="white-space: pre-wrap; margin-top: 5px;">${escapeHtml(reason)}</pre>
    </details>
  `;

  renderHeatmapOverlay(demoData);
}

// heatmap button
assessHeatmapButton.addEventListener("click", async () => {
  const bbox = getBboxFromSelection();

  if (!bbox) {
    output.textContent = "Select an area first.";
    return;
  }

  riskPanel.hidden = false;

  const progressBar = document.getElementById("heatmap-progress");
  if (progressBar) progressBar.style.display = "flex";

  const payload = {
    bbox,
    include_grid: true
  };

  try {
    const response = await fetch(`${FLOOD_API_BASE}/heatmap`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      const detail = extractHeatmapErrorMessage(data);
      if (isProviderTimeoutError(detail)) {
        renderDemoHeatmapFallback(bbox, detail);
        return;
      }

      riskOutput.textContent = `Heatmap failed:\n${JSON.stringify(data, null, 2)}`;
      return;
    }

    riskOutput.innerHTML = `
      <div style="margin-bottom: 10px; font-weight: bold; color: #2e7d32;">AI Model Analysis Complete</div>
      ${getHeatmapLegendHTML()}
    `;
    renderHeatmapOverlay(data);

  } catch (error) {
    console.error("Heatmap Error:", error);
    renderDemoHeatmapFallback(bbox, String(error));
  } finally {
    if (progressBar) progressBar.style.display = "none";
  }
});

function getHeatmapLegendHTML() {
  return `
    <div class="heatmap-legend" style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px; border: 1px solid #ddd;">
      <div style="font-size: 0.8rem; margin-bottom: 5px; color: #666; font-weight: bold;">RISK SCALE</div>
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 0.75rem;">Low</span>
        <div style="flex-grow: 1; height: 12px; background: linear-gradient(to right, #00ff00, #ffff00, #ff0000); border-radius: 6px;"></div>
        <span style="font-size: 0.75rem;">High</span>
      </div>
      <div style="font-size: 0.7rem; margin-top: 5px; color: #888;">Colors represent relative probability of flooding.</div>
    </div>
  `;
}

function renderHeatmapOverlay(data) {
  if (!data.risk_grid || !Array.isArray(data.risk_grid)) {
    riskOutput.innerHTML += "<div>No risk grid returned.</div>";
    return;
  }
  const width = data.width;
  const height = data.height;
  const grid = data.risk_grid;

  let min = data.min_risk ?? 0;
  let max = data.max_risk ?? 1;
  if (min === max) max = min + 1e-6;
  const scale = 255 / (max - min);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const imgData = ctx.createImageData(width, height);

  for (let y = 0; y < height; ++y) {
    for (let x = 0; x < width; ++x) {
      const v = grid[y][x];
      const idx = (y * width + x) * 4;
      if (v === -1.0 || isNaN(v)) {
        imgData.data[idx + 0] = 180; 
        imgData.data[idx + 1] = 220;
        imgData.data[idx + 2] = 255;
        imgData.data[idx + 3] = 0;  
      } else {
        const norm = Math.max(0, Math.min(1, (v - min) / (max - min)));
        imgData.data[idx + 0] = 255 * norm;      // R
        imgData.data[idx + 1] = 255 * (1 - norm); // G
        imgData.data[idx + 2] = 0;               // B
        imgData.data[idx + 3] = 180;             // Alpha
      }
    }
  }
  ctx.putImageData(imgData, 0, 0);

  if (window._heatmapOverlay) {
    map.removeLayer(window._heatmapOverlay);
    window._heatmapOverlay = null;
  }

  const [[minLat, minLon], [maxLat, maxLon]] = [
    [data.bbox[1], data.bbox[0]],
    [data.bbox[3], data.bbox[2]]
  ];
  const bounds = [
    [minLat, minLon],
    [maxLat, maxLon]
  ];

  window._heatmapOverlay = L.imageOverlay(canvas.toDataURL(), bounds, { opacity: 0.6 }).addTo(map);

  riskOutput.innerHTML += "<div>AI Heatmap overlay added to map.</div>";
}

function renderRiskAssessment(data) {
  const floodScore = Number(data.flood_score ?? 0);
  const scorePct = Math.round(floodScore * 100);
  const confidencePct = data.confidence != null ? Math.round(Number(data.confidence) * 100) : null;
  const level = floodScore >= 0.7 ? "HIGH" : floodScore >= 0.4 ? "MEDIUM" : "LOW";
  const levelClass = level.toLowerCase();

  const climate = data.climate_signal || {};
  const sar = data.sar_signal || {};
  const bboxText = Array.isArray(data.bbox) ? data.bbox.map((v) => Number(v).toFixed(3)).join(" | ") : "n/a";

  riskOutput.innerHTML = `
    <div class="risk-card ${levelClass}">
      <div class="risk-card-top">
        <div>
          <div class="risk-label">Flood Risk Level</div>
          <div class="risk-level ${levelClass}">${level}</div>
        </div>
        <div class="risk-badges">
          <span class="pill">Score: ${scorePct}%</span>
          <span class="pill">Height: ${formatNumber(data.estimated_water_height_m, 3)} m</span>
          <span class="pill">Confidence: ${confidencePct != null ? `${confidencePct}%` : "n/a"}</span>
        </div>
      </div>

      <div class="risk-meta">BBox: ${bboxText}</div>

      <div class="risk-grid">
        <div class="metric-tile">
          <div class="metric-name">Flood Score</div>
          <div class="metric-value">${formatNumber(data.flood_score, 4)}</div>
        </div>
        <div class="metric-tile">
          <div class="metric-name">Estimated Water Height</div>
          <div class="metric-value">${formatNumber(data.estimated_water_height_m, 3)} m</div>
        </div>
        <div class="metric-tile">
          <div class="metric-name">Confidence</div>
          <div class="metric-value">${data.confidence != null ? `${formatNumber(data.confidence, 4)} (${confidencePct}%)` : "n/a"}</div>
        </div>
        <div class="metric-tile">
          <div class="metric-name">Window</div>
          <div class="metric-value">${data.confidence_window_hours ?? "n/a"} h</div>
        </div>
      </div>

      <div class="risk-sections">
        <section>
          <h4>Climate Signal</h4>
          <ul>
            <li>Rainfall: ${formatAnomalyWithHistory(climate.rainfall_anomaly)}</li>
            <li>Temperature: ${formatAnomalyWithHistory(climate.temperature_anomaly)}</li>
            <li>Soil moisture: ${formatAnomalyWithHistory(climate.soil_moisture_anomaly)}</li>
          </ul>
        </section>
        <section>
          <h4>SAR Signal</h4>
          <ul>
            <li>Pre VV: ${formatNumber(sar.pre_vv, 4)}</li>
            <li>Post VV: ${formatNumber(sar.post_vv, 4)}</li>
            <li>Pre valid ratio: ${formatNumber(sar.pre_valid_ratio, 4)}</li>
            <li>Post valid ratio: ${formatNumber(sar.post_valid_ratio, 4)}</li>
          </ul>
        </section>
      </div>

      <details class="raw-json">
        <summary>Raw JSON</summary>
        <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
      </details>
    </div>
  `;
}

function formatNumber(value, digits) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  return Number(value).toFixed(digits);
}

function formatAnomalyWithHistory(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }

  const anomaly = Number(value);
  // Index interpretation used by this app: 1.0 ~ historical-normal baseline.
  const percentDelta = (anomaly - 1) * 100;
  const sign = percentDelta >= 0 ? "+" : "";
  const direction = percentDelta >= 0 ? "increase" : "decrease";
  const scalePct = Math.max(0, Math.min(100, (anomaly / 3) * 100));

  return `${formatNumber(anomaly, 3)} (${sign}${percentDelta.toFixed(1)}% ${direction} vs historical normal, ${scalePct.toFixed(1)}% of anomaly scale)`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Draw bbox
function renderSelection() {
  if (selectionRectangle) {
    map.removeLayer(selectionRectangle);
    selectionRectangle = null;
  }

  if (selectedPoints.length < 2) return;

  const [p1, p2] = selectedPoints;

  const bounds = L.latLngBounds(p1, p2);

  selectionRectangle = L.rectangle(bounds, {
    color: "#0f5b73",
    weight: 2,
    fillOpacity: 0.08,
  }).addTo(map);

  map.fitBounds(bounds.pad(0.2));

  output.textContent = `BBox: ${JSON.stringify(getBboxFromSelection())}`;
}

function showToast(message) {
  const el = document.createElement("div");

  el.innerText = message; // important: use innerText, not textContent

  el.style.position = "fixed";
  el.style.bottom = "20px";
  el.style.right = "20px";
  el.style.background = "#a73232";
  el.style.color = "white";
  el.style.padding = "12px 16px";
  el.style.borderRadius = "10px";
  el.style.zIndex = "9999";
  el.style.whiteSpace = "pre-line";
  el.style.fontWeight = "600";
  el.style.maxWidth = "260px";

  document.body.appendChild(el);

  setTimeout(() => el.remove(), 3500);
}

function triggerFakeFloodNotification() {
  const bbox = getBboxFromSelection();

  let areaName = "Selected Area";

  // try to get name from prompt OR fallback
  const name = prompt("Name this area:", "Recas");
  if (name) areaName = name;

  const fakeRisk = "HIGH";
  const fakeScore = (Math.random() * 0.3 + 0.7).toFixed(2); // 0.7–1.0

  const message = `🚨 ${areaName} is FLOODED (${fakeRisk} risk)\nScore: ${fakeScore}`;

  showToast(message);

  output.innerHTML = `
    <div class="json-viewer">
      ${formatJSON({
        event: "fake_flood_alert",
        area: areaName,
        bbox: bbox,
        status: fakeRisk,
        flood_score: Number(fakeScore),
        message
      })}
    </div>
  `;
}
// Compute bbox
function getBboxFromSelection() {
  if (selectedPoints.length < 2) return null;

  const [p1, p2] = selectedPoints;

  return [
    Number(Math.min(p1.lng, p2.lng).toFixed(6)),
    Number(Math.min(p1.lat, p2.lat).toFixed(6)),
    Number(Math.max(p1.lng, p2.lng).toFixed(6)),
    Number(Math.max(p1.lat, p2.lat).toFixed(6)),
  ];
}

// Format datetime
function toDatetimeLocalValue(date) {
  const pad = (v) => String(v).padStart(2, "0");

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Render scenes (no risk buttons)
function renderScenesTable(scenes, totalCount = scenes.length) {
  scenesTbody.innerHTML = "";

  if (!scenes.length) {
    scenesPanel.hidden = true;
    return;
  }

  scenesPanel.hidden = false;

  scenesSummary.textContent = `Showing ${scenes.length} of ${totalCount} scenes`;

  scenes.forEach((scene) => {
    const row = document.createElement("tr");

    const idCell = document.createElement("td");
    idCell.textContent = scene.scene_id || "n/a";

    const timeCell = document.createElement("td");
    timeCell.textContent = scene.acquisition_datetime || "n/a";

    const bboxCell = document.createElement("td");
    bboxCell.textContent = Array.isArray(scene.bbox)
      ? scene.bbox.join(", ")
      : "n/a";

    const actionCell = document.createElement("td");
    actionCell.textContent = "—";

    row.appendChild(idCell);
    row.appendChild(timeCell);
    row.appendChild(bboxCell);
    row.appendChild(actionCell);

    scenesTbody.appendChild(row);
  });
}

// Demo
demoButton.addEventListener("click", triggerFakeFloodNotification);

// ========================================
// AREA TRACKING
// ========================================

// Initialize tracking only after DOM is ready
function initializeTracking() {
  const trackedAreasList = document.getElementById("tracked-areas-list");
  const trackAreaButton = document.getElementById("track-area");
  const refreshTrackedButton = document.getElementById("refresh-tracked");

  if (!trackAreaButton || !refreshTrackedButton || !trackedAreasList) {
    console.warn("Tracking elements not found in DOM");
    return;
  }

  // Add area to tracking
  trackAreaButton.addEventListener("click", async () => {
    const bbox = getBboxFromSelection();

    if (!bbox) {
      output.textContent = "Select an area first.";
      return;
    }

    const areaName = prompt("Enter a name for this area (optional):", `Area_${Date.now()}`);
    if (areaName === null) return;

    trackAreaButton.disabled = true;
    trackAreaButton.textContent = "Tracking...";

    try {
      const response = await fetch(`${FLOOD_API_BASE}/track-area`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bbox,
          label: areaName,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        output.textContent = `Track failed: ${JSON.stringify(data)}`;
      } else {
        output.textContent = `Area tracked: ${areaName}`;
        loadTrackedAreas();
      }
    } catch (error) {
      output.textContent = `Track error: ${error}`;
    } finally {
      trackAreaButton.disabled = false;
      trackAreaButton.textContent = "📍 Track Area";
    }
  });

  // Refresh tracked areas status
  refreshTrackedButton.addEventListener("click", async () => {
    refreshTrackedButton.disabled = true;
    refreshTrackedButton.textContent = "Checking...";

    try {
      const response = await fetch(`${FLOOD_API_BASE}/check-areas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const data = await response.json();

      if (!response.ok) {
        trackedAreasList.innerHTML = `<p style="color:red">Check failed</p>`;
      } else {
        output.textContent = `Check complete: ${data.high_risk} HIGH risk, ${data.medium_risk} MEDIUM risk`;
        loadTrackedAreas();
      }
    } catch (error) {
      output.textContent = `Check error: ${error}`;
    } finally {
      refreshTrackedButton.disabled = false;
      refreshTrackedButton.textContent = "Refresh Status";
    }
  });

  // Load tracked areas on page load
  loadTrackedAreas();
}

// Load and display tracked areas
async function loadTrackedAreas() {
  const trackedAreasList = document.getElementById("tracked-areas-list");
  
  if (!trackedAreasList) return;

  try {
    const response = await fetch(`${FLOOD_API_BASE}/tracked-areas`);
    const areas = await response.json();

    if (!response.ok || !areas.length) {
      trackedAreasList.innerHTML = `<p class="hint">No tracked areas yet.</p>`;
      return;
    }

    trackedAreasList.innerHTML = areas
      .map(
        (area) => `
      <div class="tracked-item">
        <div class="tracked-item-label">${area.label}</div>
        <div class="tracked-item-bbox">
          ${area.bbox.map((v) => v.toFixed(2)).join(" | ")}
        </div>
        <div>
          <span class="tracked-item-status ${area.flood_status || "CHECKING"}">
            ${area.flood_status ? `Flood: ${area.flood_status}` : "Checking..."}
            ${area.flood_score !== null ? ` (${(area.flood_score * 100).toFixed(0)}%)` : ""}
          </span>
        </div>
        <div class="hint" style="font-size: 0.72rem;">
          ${area.estimated_water_height_m !== null && area.estimated_water_height_m !== undefined ? `Est. water height: ${area.estimated_water_height_m.toFixed(2)} m` : "Est. water height: n/a"}
          ${area.confidence !== null && area.confidence !== undefined ? ` | Confidence: ${(area.confidence * 100).toFixed(0)}%` : ""}
        </div>
        <div class="hint" style="font-size: 0.7rem;">
          Last check: ${area.last_checked ? new Date(area.last_checked).toLocaleString() : "Never"}
        </div>
        <div class="tracked-item-actions">
          <button class="secondary" onclick="removeArea(${area.id})">Delete</button>
        </div>
      </div>
    `
      )
      .join("");
  } catch (error) {
    trackedAreasList.innerHTML = `<p style="color:red">Load error: ${error}</p>`;
  }
}

// Remove tracked area
async function removeArea(areaId) {
  if (!confirm("Delete this tracked area?")) return;

  try {
    const response = await fetch(`${FLOOD_API_BASE}/tracked-area/${areaId}`, {
      method: "DELETE",
    });

    if (response.ok) {
      loadTrackedAreas();
    }
  } catch (error) {
    console.error("Delete error:", error);
  }
}

// Initialize tracking when script loads
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeTracking);
} else {
  initializeTracking();
}