document.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("glucoseChart");
  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  let labels = [];
  let values = [];
  try {
    labels = JSON.parse(document.getElementById("glucose-labels").textContent);
    values = JSON.parse(document.getElementById("glucose-values").textContent);
  } catch (error) {
    labels = [];
    values = [];
  }
  const unitLabel = canvas.dataset.unitLabel || "";

  const ctx = canvas.getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: `Glucose (${unitLabel})`,
          data: values,
          borderColor: "#00a896",
          backgroundColor: "rgba(0, 168, 150, 0.14)",
          tension: 0.3,
          fill: true,
          pointRadius: 4,
          pointBackgroundColor: "#00a896",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: "#028090",
          pointHoverBorderColor: "#ffffff",
          pointHoverBorderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: true,
          labels: {
            color: "#16324f",
            font: {
              size: 14,
              family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
            },
            padding: 15,
          },
        },
        tooltip: {
          backgroundColor: "#16324f",
          titleColor: "#ffffff",
          bodyColor: "#ffffff",
          padding: 12,
          cornerRadius: 6,
          titleFont: {
            size: 14,
            weight: "bold",
          },
          bodyFont: {
            size: 13,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          ticks: {
            color: "#46627a",
            font: {
              size: 12,
            },
          },
          grid: {
            color: "#e2f5f2",
            borderColor: "#c5e9e6",
            borderWidth: 1,
          },
        },
        x: {
          ticks: {
            color: "#46627a",
            font: {
              size: 12,
            },
          },
          grid: {
            color: "#e2f5f2",
            borderColor: "#c5e9e6",
            borderWidth: 1,
          },
        },
      },
    },
  });
});
