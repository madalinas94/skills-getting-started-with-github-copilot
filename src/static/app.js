const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const dropzoneTitle = document.getElementById("dropzone-title");
const uploadStatus = document.getElementById("upload-status");
const results = document.getElementById("results");

const CHART_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];

const state = { hash: null };

function formatNumber(value) {
  return Number(value).toLocaleString("ro-RO", { maximumFractionDigits: 2 });
}

function setStatus(message, isError = false) {
  uploadStatus.textContent = message;
  uploadStatus.classList.toggle("error", isError);
}

async function uploadFile(file) {
  if (!file) return;
  dropzoneTitle.textContent = file.name;
  setStatus("Se procesează CSV-ul...");
  results.classList.add("hidden");

  const formData = new FormData();
  formData.append("file", file);

  let res;
  try {
    res = await fetch("/upload", { method: "POST", body: formData });
  } catch (err) {
    setStatus("Eroare de rețea — încearcă din nou.", true);
    return;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Eroare necunoscută" }));
    setStatus(`Eroare: ${body.detail}`, true);
    return;
  }

  const data = await res.json();
  state.hash = data.hash;
  setStatus(`Gata — ${data.row_count} rânduri curate.`);
  render(data);

  const tableRes = await fetch(`/data/${data.hash}`);
  const full = await tableRes.json();
  renderTable(full.table, full.columns, full.anomalies);
}

function render(data) {
  results.classList.remove("hidden");
  renderReport(data.report);
  renderStats(data.aggregates, data.row_count);
  renderAnomaliesSummary(data.anomalies);
  renderCharts(data.aggregates.top_by, data.aggregates.value_column);
}

function renderReport(report) {
  const parts = [
    `din ${report.rows_in} rânduri am păstrat ${report.rows_out}`,
    `${report.blank_rows_removed} goale eliminate`,
    `${report.total_rows_removed} rânduri de total eliminate`,
    `${report.duplicate_rows_removed} duplicate eliminate`,
  ];
  const variantCols = Object.keys(report.name_variants_merged || {});
  if (variantCols.length) {
    const count = variantCols.reduce(
      (sum, col) => sum + Object.values(report.name_variants_merged[col]).flat().length,
      0
    );
    parts.push(`${count} variante de scriere unificate (${variantCols.join(", ")})`);
  }
  document.getElementById("report-text").textContent = parts.join(" · ") + ".";
}

function renderStats(aggregates, rowCount) {
  const container = document.getElementById("stat-tiles");
  container.innerHTML = "";

  const tile = (label, value) => {
    const el = document.createElement("div");
    el.className = "stat-tile";
    el.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
    return el;
  };

  container.appendChild(tile("Rânduri curate", formatNumber(rowCount)));

  const valueCol = aggregates.value_column;
  if (valueCol && aggregates.stats[valueCol]) {
    const s = aggregates.stats[valueCol];
    container.appendChild(tile(`Total ${valueCol}`, formatNumber(s.sum)));
    container.appendChild(tile(`Medie ${valueCol}`, formatNumber(s.mean)));
    container.appendChild(tile(`Maxim ${valueCol}`, formatNumber(s.max)));
  }
}

function renderAnomaliesSummary(anomalies) {
  const container = document.getElementById("anomalies-list");
  container.innerHTML = "";
  if (!anomalies || anomalies.length === 0) {
    container.innerHTML = '<p class="anomalies-empty">Nicio valoare neobișnuită găsită.</p>';
    return;
  }
  anomalies.slice(0, 8).forEach((a) => {
    const el = document.createElement("div");
    el.className = "anomaly-item";
    el.innerHTML = `<span class="icon">!</span><span>Rând ${a.row + 1}: <strong>${a.column}</strong> = ${formatNumber(
      a.value
    )} (interval așteptat ${formatNumber(a.bounds[0])} – ${formatNumber(a.bounds[1])})</span>`;
    container.appendChild(el);
  });
  if (anomalies.length > 8) {
    const more = document.createElement("p");
    more.className = "anomalies-empty";
    more.textContent = `+ încă ${anomalies.length - 8} valori neobișnuite.`;
    container.appendChild(more);
  }
}

function renderCharts(topBy, valueColumn) {
  const container = document.getElementById("charts");
  container.innerHTML = "";
  if (!topBy) return;

  const columns = Object.keys(topBy).filter((col) => topBy[col] && topBy[col].length > 0);
  columns.forEach((col, i) => {
    const entries = topBy[col].slice(0, 8);
    const max = Math.max(...entries.map((e) => e.value));
    const color = CHART_COLORS[i % CHART_COLORS.length];

    const card = document.createElement("div");
    card.className = "chart-card";
    const title = document.createElement("h3");
    title.textContent = `Top ${col} după ${valueColumn || "valoare"}`;
    card.appendChild(title);

    entries.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "bar-row";
      const pct = max > 0 ? Math.max((entry.value / max) * 100, 2) : 0;
      row.innerHTML = `
        <span class="bar-label" title="${entry.key}">${entry.key}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${pct}%; --bar-color:${color}"></span></span>
        <span class="bar-value">${formatNumber(entry.value)}</span>
      `;
      card.appendChild(row);
    });

    container.appendChild(card);
  });
}

function renderTable(table, columns, anomalies) {
  const el = document.getElementById("data-table");
  const note = document.getElementById("table-note");
  el.innerHTML = "";

  const anomalyRows = new Set((anomalies || []).map((a) => a.row));
  const LIMIT = 200;
  const rows = table.slice(0, LIMIT);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  el.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row, idx) => {
    const tr = document.createElement("tr");
    if (anomalyRows.has(idx)) tr.classList.add("anomaly-row");
    columns.forEach((col) => {
      const td = document.createElement("td");
      const value = row[col];
      td.textContent = value === null || value === undefined ? "" : value;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  el.appendChild(tbody);

  note.textContent =
    table.length > LIMIT ? `Se arată primele ${LIMIT} din ${table.length} rânduri.` : `${table.length} rânduri.`;
}

async function askQuestion(question) {
  const answerEl = document.getElementById("ask-answer");
  if (!state.hash) {
    answerEl.textContent = "Încarcă întâi un CSV.";
    return;
  }
  answerEl.textContent = "Se gândește...";
  const res = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hash: state.hash, question }),
  });
  if (!res.ok) {
    answerEl.textContent = "Nu am putut răspunde — încearcă din nou.";
    return;
  }
  const data = await res.json();
  answerEl.textContent = data.answer;
}

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => uploadFile(fileInput.files[0]));

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

document.getElementById("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("ask-input");
  const question = input.value.trim();
  if (question) askQuestion(question);
});
