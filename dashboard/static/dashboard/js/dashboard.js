/* Glucose trend chart.

   Colours come from the theme tokens rather than fixed hex values, so the
   chart follows the light/dark switch (main/js/theme.js fires themechange). */

(function () {
  const canvas = document.getElementById("glucoseChart");
  if (!canvas) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const token = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const readJSON = (id) => {
    try {
      return JSON.parse(document.getElementById(id).textContent);
    } catch (error) {
      return [];
    }
  };

  let chart = null;

  const draw = () => {
    if (typeof Chart === "undefined" || chart) return;

    const labels = readJSON("glucose-labels");
    const values = readJSON("glucose-values");
    const unitLabel = canvas.dataset.unitLabel || "";
    const accent = token("--accent");
    const grid = token("--line-soft");

    if (chart) chart.destroy();

    chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: `Glucose (${unitLabel})`,
            data: values,
            borderColor: accent,
            backgroundColor: token("--accent-soft"),
            tension: 0.3,
            fill: true,
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: accent,
            pointBorderColor: token("--surface"),
            pointBorderWidth: 2,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        animation: reducedMotion ? false : { duration: 900 },
        plugins: {
          legend: {
            display: true,
            labels: { color: token("--ink-2"), boxWidth: 12, boxHeight: 12, padding: 14 },
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
            ticks: { color: token("--ink-3") },
            grid: { color: grid },
            border: { display: false },
          },
          x: {
            ticks: { color: token("--ink-3") },
            grid: { display: false },
            border: { color: grid },
          },
        },
      },
    });
  };

  const repaint = () => {
    if (!chart) return;
    const accent = token("--accent");
    const dataset = chart.data.datasets[0];

    dataset.borderColor = accent;
    dataset.backgroundColor = token("--accent-soft");
    dataset.pointBackgroundColor = accent;
    dataset.pointBorderColor = token("--surface");

    chart.options.plugins.legend.labels.color = token("--ink-2");
    chart.options.plugins.tooltip.backgroundColor = token("--ink");
    chart.options.plugins.tooltip.titleColor = token("--paper");
    chart.options.plugins.tooltip.bodyColor = token("--paper");
    chart.options.scales.y.ticks.color = token("--ink-3");
    chart.options.scales.y.grid.color = token("--line-soft");
    chart.options.scales.x.ticks.color = token("--ink-3");
    chart.options.scales.x.border.color = token("--line-soft");

    chart.update("none");
  };

  document.addEventListener("DOMContentLoaded", draw);
  document.addEventListener("themechange", repaint);
})();
