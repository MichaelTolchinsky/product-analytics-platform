const API = "";

const C = {
  blue:   "#5b8af5",
  purple: "#9b72f5",
  green:  "#3ecf8e",
  orange: "#f5a623",
  pink:   "#f472b6",
  sub:    "#8891aa",
  grid:   "rgba(255,255,255,0.06)",
};

const PALETTE = [C.blue, C.purple, C.pink, C.orange, C.green];

function tooltip() {
  return {
    backgroundColor: "#2e3347",
    titleColor: "#e4e7f0",
    bodyColor: "#8891aa",
    borderColor: "rgba(255,255,255,0.1)",
    borderWidth: 1,
    padding: 10,
    cornerRadius: 8,
  };
}

function scales(horizontal) {
  const axis = {
    ticks: { color: C.sub, font: { size: 11, family: "Inter, system-ui" } },
    grid: { color: C.grid },
    border: { display: false },
  };
  // Return independent objects — never share references
  return horizontal
    ? { x: { ...axis, ticks: { ...axis.ticks } }, y: { ...axis, ticks: { ...axis.ticks } } }
    : { x: { ...axis, ticks: { ...axis.ticks } }, y: { ...axis, ticks: { ...axis.ticks } } };
}

// ---------------------------------------------------------------------------
// Fetch — allSettled so one 500 doesn't blank the whole page
// ---------------------------------------------------------------------------

async function get(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

async function fetchAll() {
  const endpoints = [
    "/metrics/dau",
    "/metrics/conversion",
    "/metrics/events",
    "/metrics/top-pages",
    "/metrics/searches",
  ];
  const settled = await Promise.allSettled(endpoints.map(get));
  return settled.map((r, i) => {
    if (r.status === "rejected") {
      console.warn("fetch failed:", endpoints[i], r.reason);
      return null;
    }
    return r.value;
  });
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

function renderDAU(data) {
  if (!data) return;
  document.getElementById("dau-value").textContent =
    parseInt(data.dau, 10).toLocaleString();
  document.getElementById("dau-date").textContent =
    data.date ? `as of ${data.date}` : "";
}

function renderConversion(data) {
  if (!data) return;
  const pct = parseFloat(data.conversion_rate_pct);
  document.getElementById("conversion-rate").textContent =
    isNaN(pct) ? "—" : `${pct.toFixed(1)}%`;
  document.getElementById("conversion-sub").textContent =
    `${parseInt(data.converted_sessions, 10).toLocaleString()} of ` +
    `${parseInt(data.total_signup_sessions, 10).toLocaleString()} signup sessions`;
  const badge = document.getElementById("conversion-badge");
  badge.textContent = pct >= 10 ? "Strong" : pct >= 5 ? "Moderate" : "Low";
  badge.className   = "badge " + (pct >= 10 ? "badge-green" : pct >= 5 ? "badge-blue" : "badge-orange");
}

function renderEvents(data) {
  if (!data) return;
  const values = data.events.map(e => parseInt(e.count, 10));
  const labels = data.events.map(e => e.event_type.replace(/_/g, " "));

  document.getElementById("total-events").textContent =
    values.reduce((a, b) => a + b, 0).toLocaleString();

  new Chart(document.getElementById("events-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: PALETTE,
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false }, tooltip: tooltip() },
      scales: scales(false),
    },
  });
}

function renderTopPages(data) {
  if (!data) return;
  const labels = data.pages.map(p => p.page);
  const values = data.pages.map(p => parseInt(p.views, 10));

  new Chart(document.getElementById("top-pages-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: C.blue, borderRadius: 6, borderSkipped: false }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: tooltip() },
      scales: scales(true),
    },
  });
}

function renderSearches(data) {
  if (!data) return;
  const labels = data.searches.map(s => s.query);
  const values = data.searches.map(s => parseInt(s.count, 10));

  new Chart(document.getElementById("searches-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: C.purple, borderRadius: 6, borderSkipped: false }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: tooltip() },
      scales: scales(true),
    },
  });
}

// ---------------------------------------------------------------------------
// Boot — wait for DOM before touching canvas elements
// ---------------------------------------------------------------------------

async function load() {
  const [dau, conversion, events, topPages, searches] = await fetchAll();
  renderDAU(dau);
  renderConversion(conversion);
  renderEvents(events);
  renderTopPages(topPages);
  renderSearches(searches);
  document.getElementById("last-updated").textContent =
    `Updated ${new Date().toLocaleTimeString()}`;
}

document.addEventListener("DOMContentLoaded", load);
