//const $ = (sel) => document.querySelector(sel);
//const $list = (sel) => document.querySelectorAll(sel);
const $ = (sel) => document.querySelector(sel);

const queryEl = $("#query");
const suggEl = $("#suggestions");
const currentEl = $("#current");
const forecastEl = $("#forecast");
const btnF = $("#btnF");
const btnC = $("#btnC");
const useLocBtn = $("#useLocation");
const startInput = $("#startDate");
const endInput = $("#endDate");
const saveBtn = $("#saveReq");
const refreshBtn = $("#refreshSaved");
const savedListEl = $("#savedList");

let UNIT = "fahrenheit"; // default

// Temperature Unit toggle functionality
function setUnit(u) {
  UNIT = u;
  btnF.classList.toggle("active", u === "fahrenheit");
  btnC.classList.toggle("active", u === "celsius");
}

// Toggle unit to fahrenheit
btnF.addEventListener("click", () => {
  setUnit("fahrenheit");
  const card = currentEl.dataset.coords;
  if (card) {
    const { lat, lon } = JSON.parse(card);
    fetchWeather(lat, lon);
  }
});

// Toggle unit to celsius
btnC.addEventListener("click", () => {
  setUnit("celsius");
  const card = currentEl.dataset.coords;
  if (card) {
    const { lat, lon } = JSON.parse(card);
    fetchWeather(lat, lon);
  }
});

// Autocomplete functionality
let acTimer; let lastAC = "";
queryEl.addEventListener("input", () => {
  const q = queryEl.value.trim();
  clearTimeout(acTimer);
  if (q.length < 3) { suggEl.classList.remove("show"); suggEl.innerHTML = ""; return; }
  acTimer = setTimeout(async () => {
    try {
      if (q === lastAC) return;
      lastAC = q;
      const res = await fetch(`/api/autocomplete?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (data.error) {
        suggEl.innerHTML = `<li>${escapeHtml(data.error)}</li>`;
        suggEl.classList.add("show");
        return;
      }
      const items = (data.suggestions || []).map(s => {
        const disabled = s.disabled ? ' aria-disabled="true" class="disabled"' : '';
        return `<li data-lat="${s.lat}" data-lon="${s.lon}"${disabled}>${escapeHtml(s.label)}</li>`;
      }).join("");
      if (items) {
        suggEl.innerHTML = items;
        suggEl.classList.add("show");
      } else {
        suggEl.classList.remove("show");
        suggEl.innerHTML = "";
      }
    } catch (e) {
      suggEl.innerHTML = `<li>Autocomplete error. Try again.</li>`;
      suggEl.classList.add("show");
    }
  }, 750);
});

// Enter autocomplete suggestion
suggEl.addEventListener("click", (e) => {
  const li = e.target.closest("li");
  if (!li || li.classList.contains("disabled")) return;
  const lat = parseFloat(li.dataset.lat);
  const lon = parseFloat(li.dataset.lon);
  queryEl.value = li.textContent;
  suggEl.classList.remove("show");
  fetchWeather(lat, lon);
});

// Search enter button call
queryEl.addEventListener("keydown", async (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    const q = queryEl.value.trim();
    console.log(q);
    if (!q) return;
    try {
      const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
      const g = await res.json();
      if (g.lat && g.lon) {
        fetchWeather(g.lat, g.lon);
      } else {
        showError(g.error || "No results");
      }
    } catch(err){
      showError("Geocoding failed");
    }
  }
});

// Use current location button
useLocBtn.addEventListener("click", () => {
  if (!navigator.geolocation) {
    return showError("Geolocation not supported in this browser.");
  }
  navigator.geolocation.getCurrentPosition((pos) => {
    const { latitude, longitude } = pos.coords;
    fetchWeather(latitude, longitude);
  }, (err) => {
    showError("Location permission denied or unavailable.");
  }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 });
});

// function for getting weather data
async function fetchWeather(lat, lon) {
  currentEl.innerHTML = `<div class="loading">Loading weather…</div>`;
  try {
    const res = await fetch(`/api/weather?lat=${lat}&lon=${lon}&unit=${UNIT}`);
    const data = await res.json();
    if (data.error) { showError(data.error); return; }
    currentEl.dataset.coords = JSON.stringify({ lat, lon });
    renderCurrent(data.current, data.unit);
    renderForecast(data.daily, data.unit);
  } catch (e) {
    showError("Failed to load weather.");
  }
}

// Renders the current weather
function renderCurrent(c, unit) {
  const tempUnit = unit === "fahrenheit" ? "°F" : "°C";
  const windUnit = unit === "fahrenheit" ? "mph" : "km/h";
  const precipUnit = unit === "fahrenheit" ? "in" : "mm";

  currentEl.innerHTML = `
    <div class="row">
      <i class="big ${c.icon}"></i>
      <div>
        <div class="h1" style="font-size:32px; font-weight:800;">${Math.round(c.temperature)}${tempUnit} · ${escapeHtml(c.code_text)}</div>
        <div style="color:#8aa0b6; margin-top:4px;">Feels like ${Math.round(c.apparent_temperature)}${tempUnit} · ${new Date(c.time).toLocaleString()}</div>
      </div>
    </div>
    <div class="meta">
      ${stat("Humidity", `${c.humidity}%`)}
      ${stat("Wind", `${Math.round(c.wind_speed)} ${windUnit} ${degToCompass(c.wind_dir)}`)}
      ${stat("Precipitation", `${c.precipitation ?? 0} ${precipUnit}`)}
      ${stat("Cloud Cover", `${c.cloud_cover}%`)}
      ${stat("Pressure", `${Math.round(c.pressure)} hPa`)}
    </div>
  `;
}

// Renders weather forecast for next days
function renderForecast(days, unit) {
  const tempUnit = unit === "fahrenheit" ? "°F" : "°C";
  forecastEl.innerHTML = days.map(d => `
    <div class="day">
      <div>${new Date(d.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</div>
      <i class="${d.icon}"></i>
      <div>${escapeHtml(d.code_text)}</div>
      <div class="t">${Math.round(d.t_max)}${tempUnit} / ${Math.round(d.t_min)}${tempUnit}</div>
      <div class="pop">💧 ${d.pop ?? 0}% · 💨 ${Math.round(d.wind_max)} ${unit === 'fahrenheit' ? 'mph' : 'km/h'}</div>
    </div>
  `).join("");
}

function stat(label, value){
  return `<div class="stat"><label>${escapeHtml(label)}</label><div class="value">${escapeHtml(String(value))}</div></div>`;
}

function showError(msg){
  currentEl.innerHTML = `<div class="loading">${escapeHtml(msg)}</div>`;
}

function degToCompass(deg){
  if (deg == null) return "";
  const val = Math.floor((deg / 22.5) + 0.5);
  const arr = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]; 
  return arr[val % 16];
}

function escapeHtml(s){
  return s.replace(/[&<>"]|\u2028|\u2029/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\u2028':'\\u2028','\u2029':'\\u2029'}[c]));
}

if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition((pos) => {
    fetchWeather(pos.coords.latitude, pos.coords.longitude);
  });
}

function iso(d){ return d?.toString().slice(0,10); }
function today(){ return new Date().toISOString().slice(0,10); }
function ensureDates(){
  const s = startInput.value, e = endInput.value;
  if (!s || !e) throw new Error("Please select both start and end dates.");
  if (e < s) throw new Error("End date must be on/after start date.");
  return { start_date: s, end_date: e };
}

async function saveRequest() {
  try {
    const { start_date, end_date } = ensureDates();
    let body;
    // Prefer the last fetched coords if available
    const coordsStr = currentEl.dataset.coords;
    if (coordsStr) {
      const { lat, lon } = JSON.parse(coordsStr);
      body = { lat, lon, label: $("#query").value || undefined, start_date, end_date, unit: UNIT };
    } else {
      // Otherwise, use the text query and let the server resolve it once
      const q = $("#query").value.trim();
      if (!q) throw new Error("Enter a location or fetch weather first.");
      body = { query: q, start_date, end_date, unit: UNIT };
    }
    const res = await fetch("/api/requests", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Save failed");
    await fetchSaved(); // refresh list
  } catch (e) {
    showError(e.message || "Save failed");
  }
}