/* GlucoRead landing page behaviour.
   Everything here is either feedback for a user action or a one-shot reveal.
   No scroll listeners: position is observed with IntersectionObserver. */

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const hasObserver = "IntersectionObserver" in window;

/* --- mobile menu ---------------------------------------------------------- */
const menuBtn = document.getElementById("menuBtn");
const menu = document.getElementById("menu");

if (menuBtn && menu) {
  const closeMenu = () => {
    menu.classList.remove("open");
    menuBtn.setAttribute("aria-expanded", "false");
  };

  menuBtn.addEventListener("click", () => {
    const isOpen = menu.classList.toggle("open");
    menuBtn.setAttribute("aria-expanded", String(isOpen));
  });

  menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
}

/* --- topbar gains a border once the hero scrolls under it ------------------ */
const sentinel = document.getElementById("topSentinel");
const topbar = document.getElementById("topbar");

if (sentinel && topbar && hasObserver) {
  new IntersectionObserver(([entry]) =>
    topbar.classList.toggle("is-stuck", !entry.isIntersecting)
  ).observe(sentinel);
}

/* --- scroll reveals ------------------------------------------------------- */
const revealItems = document.querySelectorAll(".reveal");

if (reducedMotion || !hasObserver) {
  revealItems.forEach((item) => item.classList.add("show"));
} else {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("show");
        revealObserver.unobserve(entry.target);
      });
    },
    { threshold: 0.18 }
  );

  revealItems.forEach((item) => revealObserver.observe(item));
}

/* --- unit switch ----------------------------------------------------------
   Mirrors the app: values are held in mmol/L and converted only for display.
   1 mmol/L = 18.0182 mg/dL. */
const MGDL_PER_MMOL = 18.0182;
const unitButtons = document.querySelectorAll("[data-unit]");
const unitValues = document.querySelectorAll(".unit-value");

const renderUnit = (unit) => {
  unitValues.forEach((node) => {
    const mmol = Number.parseFloat(node.dataset.mmol);
    if (Number.isNaN(mmol)) return;

    node.textContent =
      unit === "mgdl" ? String(Math.round(mmol * MGDL_PER_MMOL)) : mmol.toFixed(1);

    if (reducedMotion) return;
    node.classList.remove("is-swapping");
    void node.offsetWidth; // restart the swap animation
    node.classList.add("is-swapping");
  });
};

unitButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-pressed") === "true") return;

    unitButtons.forEach((other) =>
      other.setAttribute("aria-pressed", String(other === button))
    );

    renderUnit(button.dataset.unit);
  });
});

/* --- dashboard preview chart ----------------------------------------------
   The same Chart.js line the dashboard draws, given example readings. Colours
   are read from the theme tokens and refreshed by repaintChart below. */
const chartCanvas = document.getElementById("demoChart");
const chartData = document.getElementById("demoChartData");
let demoChart = null;

const readDemoData = () => {
  try {
    return JSON.parse(chartData.textContent);
  } catch (error) {
    return null;
  }
};

const token = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const drawChart = () => {
  if (!chartCanvas || !chartData || typeof Chart === "undefined" || demoChart) return;

  const data = readDemoData();
  if (!data) return;

  const accent = token("--accent");
  const ink = token("--ink-2");
  const grid = token("--line-soft");
  const surface = token("--surface");
  const unitLabel = chartCanvas.dataset.unitLabel || "";

  demoChart = new Chart(chartCanvas.getContext("2d"), {
    type: "line",
    data: {
      labels: data.labels,
      datasets: [
        {
          label: `Glucose (${unitLabel})`,
          data: data.values,
          borderColor: accent,
          backgroundColor: token("--accent-soft"),
          tension: 0.3,
          fill: true,
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: accent,
          pointBorderColor: surface,
          pointBorderWidth: 2,
          pointHoverRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: reducedMotion ? false : { duration: 900 },
      plugins: {
        legend: {
          display: true,
          labels: { color: ink, boxWidth: 12, boxHeight: 12, padding: 12 },
        },
        tooltip: {
          backgroundColor: token("--ink"),
          titleColor: token("--paper"),
          bodyColor: token("--paper"),
          padding: 10,
          cornerRadius: 8,
          displayColors: false,
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          ticks: { color: token("--ink-3"), font: { size: 11 } },
          grid: { color: grid },
          border: { display: false },
        },
        x: {
          ticks: { color: token("--ink-3"), font: { size: 11 } },
          grid: { display: false },
          border: { color: grid },
        },
      },
    },
  });
};

/* Recolour the existing chart rather than rebuilding it: a fresh Chart on the
   same canvas re-measures a box the previous one already sized, which made the
   preview grow on every theme switch. */
const repaintChart = () => {
  if (!demoChart) return;

  const accent = token("--accent");
  const dataset = demoChart.data.datasets[0];

  dataset.borderColor = accent;
  dataset.backgroundColor = token("--accent-soft");
  dataset.pointBackgroundColor = accent;
  dataset.pointBorderColor = token("--surface");

  demoChart.options.plugins.legend.labels.color = token("--ink-2");
  demoChart.options.plugins.tooltip.backgroundColor = token("--ink");
  demoChart.options.plugins.tooltip.titleColor = token("--paper");
  demoChart.options.plugins.tooltip.bodyColor = token("--paper");
  demoChart.options.scales.y.ticks.color = token("--ink-3");
  demoChart.options.scales.y.grid.color = token("--line-soft");
  demoChart.options.scales.x.ticks.color = token("--ink-3");
  demoChart.options.scales.x.border.color = token("--line-soft");

  demoChart.update("none");
};

if (document.readyState === "complete") {
  drawChart();
} else {
  window.addEventListener("load", drawChart, { once: true });
}

document.addEventListener("themechange", repaintChart);
