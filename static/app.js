
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

let acTimer;
queryEl.addEventListener("input", () => {
  const q = queryEl.value.trim();
  clearTimeout(acTimer);
  if (!q) { suggEl.classList.remove("show"); suggEl.innerHTML = ""; return; }
  acTimer = setTimeout(async () => {
    try {
      const res = await fetch(`/api/autocomplete?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      const items = (data.suggestions || []).map(s => `<li data-lat="${s.lat}" data-lon="${s.lon}">${escapeHtml(s.label)}</li>`).join("");
      if (items) {
        suggEl.innerHTML = items;
        suggEl.classList.add("show");
      } else {
        suggEl.classList.remove("show");
      }
    } catch (e) {
      
    }
  }, 180);
});

suggEl.addEventListener("click", (e) => {
  const li = e.target.closest("li");
  if (!li) return;
  const lat = parseFloat(li.dataset.lat);
  const lon = parseFloat(li.dataset.lon);
  queryEl.value = li.textContent;
  suggEl.classList.remove("show");
  fetchWeather(lat, lon);
});