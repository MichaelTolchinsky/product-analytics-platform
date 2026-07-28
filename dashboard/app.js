const API = "";  // same origin — served by FastAPI

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e2535" } },
    y: { ticks: { color: "#94a3b8" }, grid: { color: "#1e2535" } },
  },
};

const ACCENT = "#6366f1";

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function fetchJSON(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

function renderDAU(data) {
  document.getElementById("dau-value").textContent =
    data.dau != null ? data.dau.toLocaleString() : "—";
  document.getElementById("dau-date").textContent =
    data.date ? `as of ${data.date}` : "";
}

function renderConversion(data) {
  const pct = data.conversion_rate_pct;
  document.getElementById("conversion-rate").textContent =
    pct != null ? `${parseFloat(pct).toFixed(1)}%` : "—";
  document.getElementById("conversion-sub").textContent =
    `${data.converted_sessions} / ${data.total_signup_sessions} signup sessions`;
}

function renderEvents(data) {
  const labels = data.events.map((e) => e.event_type);
  const values = data.events.map((e) => parseInt(e.count, 10));
  new Chart(document.getElementById("events-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: ACCENT, borderRadius: 4 }],
    },
    options: CHART_DEFAULTS,
  });
}

function renderTopPages(data) {
  const labels = data.pages.map((p) => p.page);
  const values = data.pages.map((p) => parseInt(p.views, 10));
  new Chart(document.getElementById("top-pages-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: ACCENT, borderRadius: 4 }],
    },
    options: { ...CHART_DEFAULTS, indexAxis: "y" },
  });
}

function renderSearches(data) {
  const labels = data.searches.map((s) => s.query);
  const values = data.searches.map((s) => parseInt(s.count, 10));
  new Chart(document.getElementById("searches-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: ACCENT, borderRadius: 4 }],
    },
    options: { ...CHART_DEFAULTS, indexAxis: "y" },
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

async function load() {
  try {
    const [dau, conversion, events, topPages, searches] = await Promise.all([
      fetchJSON("/metrics/dau"),
      fetchJSON("/metrics/conversion"),
      fetchJSON("/metrics/events"),
      fetchJSON("/metrics/top-pages"),
      fetchJSON("/metrics/searches"),
    ]);

    renderDAU(dau);
    renderConversion(conversion);
    renderEvents(events);
    renderTopPages(topPages);
    renderSearches(searches);

    document.getElementById("last-updated").textContent =
      `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.error("dashboard load failed:", err);
  }
}

load();
