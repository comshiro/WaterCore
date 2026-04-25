const API_BASE = "http://127.0.0.1:8000/api/v1/risk";
const FLOOD_API_BASE = "http://127.0.0.1:8000/api/v1/flood";

const output = document.getElementById("output");
const demoButton = document.getElementById("load-demo");
const queryScenesButton = document.getElementById("query-scenes");
const clearAreaButton = document.getElementById("clear-area");
const assessAreaButton = document.getElementById("assess-area");

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

// 🌍 Map setup
const map = L.map("map").setView([45.757, 21.23], 9);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const selectedPoints = [];
let selectionRectangle = null;
let currentScenes = [];

// ⏱️ Default time range
const now = new Date();
const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);

startInput.value = toDatetimeLocalValue(threeDaysAgo);
endInput.value = toDatetimeLocalValue(now);

// 🖱️ Map click → bbox selection
map.on("click", (event) => {
  if (selectedPoints.length === 2) {
    selectedPoints.length = 0;
  }

  selectedPoints.push(event.latlng);
  renderSelection();
});

// 🧹 Clear selection
clearAreaButton.addEventListener("click", () => {
  selectedPoints.length = 0;
  renderSelection();

  currentScenes = [];
  renderScenesTable([]);

  riskPanel.hidden = true;
  output.textContent = "Selection cleared.";
});

// 📡 Query scenes
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

// 🌐 Assess risk for entire area
assessAreaButton.addEventListener("click", async () => {
  const bbox = getBboxFromSelection();

  if (!bbox) {
    output.textContent = "Select an area first.";
    return;
  }

  if (!startInput.value || !endInput.value) {
    output.textContent = "Set date/time range.";
    return;
  }

  riskPanel.hidden = false;
  riskOutput.textContent = "Assessing risk...";

  const payload = {
    bbox,
    start_datetime: new Date(startInput.value).toISOString(),
    end_datetime: new Date(endInput.value).toISOString(),
  };

  try {
    const response = await fetch(`${API_BASE}/assess-area`, {
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

    riskOutput.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    riskOutput.textContent = `Risk request error: ${error}`;
  }
});

// 🎯 Draw bbox
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

// 📦 Compute bbox
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

// 🕒 Format datetime
function toDatetimeLocalValue(date) {
  const pad = (v) => String(v).padStart(2, "0");

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// 📋 Render scenes (no risk buttons)
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

// 🧪 Demo
demoButton.addEventListener("click", async () => {
  output.textContent = "Loading demo...";

  try {
    const response = await fetch(`${API_BASE}/demo`);
    const data = await response.json();

    output.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    output.textContent = `Demo error: ${error}`;
  }
});

// ========================================
// 📡 AREA TRACKING
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