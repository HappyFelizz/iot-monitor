const statusEl = document.getElementById('status');
const infoEl = document.getElementById('status-info');
const radarCanvas = document.getElementById('radarCanvas');
const radarCtx = radarCanvas.getContext('2d');

const campos = {
  angulo: document.getElementById('angulo'),
  distancia: document.getElementById('distancia'),
  objeto: document.getElementById('objeto'),
  portao: document.getElementById('portao'),
  deteccao: document.getElementById('deteccao'),
};

let estadoRadar = { angulo: 0, distancia: 0, deteccao: 'Objeto' };

function desenharRadar() {
  const w = radarCanvas.width;
  const h = radarCanvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const raioMax = 150;

  radarCtx.fillStyle = 'rgba(7, 17, 31, 0.8)';
  radarCtx.fillRect(0, 0, w, h);

  radarCtx.strokeStyle = 'rgba(79, 227, 165, 0.3)';
  radarCtx.lineWidth = 1;
  radarCtx.beginPath();
  radarCtx.arc(cx, cy, raioMax, 0, Math.PI);
  radarCtx.stroke();

  for (let dist = 10; dist <= 30; dist += 10) {
    const r = (dist / 30) * raioMax;
    radarCtx.beginPath();
    radarCtx.arc(cx, cy, r, 0, Math.PI);
    radarCtx.stroke();
    radarCtx.fillStyle = 'rgba(141, 164, 196, 0.4)';
    radarCtx.font = '12px Arial';
    radarCtx.fillText(dist + 'cm', cx + 5, cy - r + 15);
  }

  for (let ang = 0; ang <= 180; ang += 30) {
    const rad = (ang * Math.PI) / 180;
    const x = cx + raioMax * Math.cos(rad);
    const y = cy - raioMax * Math.sin(rad);
    radarCtx.beginPath();
    radarCtx.moveTo(cx, cy);
    radarCtx.lineTo(x, y);
    radarCtx.stroke();
  }

  const angRad = (estadoRadar.angulo * Math.PI) / 180;
  radarCtx.strokeStyle = 'rgba(79, 227, 165, 0.8)';
  radarCtx.lineWidth = 2;
  radarCtx.beginPath();
  radarCtx.moveTo(cx, cy);
  radarCtx.lineTo(cx + raioMax * Math.cos(angRad), cy - raioMax * Math.sin(angRad));
  radarCtx.stroke();

  if (estadoRadar.distancia > 0 && estadoRadar.distancia <= 30) {
    const r = (estadoRadar.distancia / 30) * raioMax;
    const x = cx + r * Math.cos(angRad);
    const y = cy - r * Math.sin(angRad);
    radarCtx.fillStyle = estadoRadar.deteccao === 'Humano' ? 'rgba(255, 107, 107, 0.9)' : 'rgba(79, 227, 165, 0.9)';
    radarCtx.beginPath();
    radarCtx.arc(x, y, 8, 0, Math.PI * 2);
    radarCtx.fill();
  }
}

function aplicarEstado(dado) {
  const serial = dado.dado || {};
  const parsed = serial.parsed || {};

  statusEl.textContent = dado.conectado ? 'online' : 'offline';
  statusEl.className = dado.conectado ? 'value online' : 'value offline';
  if (dado.conectado) {
    infoEl.textContent = dado.erro || '';
    infoEl.className = 'text-muted';
  } else {
    const ultimo = dado.ultima_conexao ? new Date(dado.ultima_conexao).toLocaleString('pt-BR') : 'desconhecido';
    infoEl.textContent = `Última conexão: ${ultimo}`;
    infoEl.className = 'text-warning';
  }

  campos.angulo.textContent = parsed.angulo ?? '-';
  campos.distancia.textContent = parsed.distancia_cm ?? '-';
  campos.objeto.textContent = parsed.temperatura_objeto_c ?? '-';
  campos.portao.textContent = parsed.portao ?? '-';
  campos.deteccao.textContent = parsed.deteccao ?? '-';

  if (parsed.angulo !== undefined && parsed.distancia_cm !== undefined) {
    estadoRadar.angulo = parsed.angulo;
    estadoRadar.distancia = parsed.distancia_cm;
    estadoRadar.deteccao = parsed.deteccao || 'Objeto';
    desenharRadar();
  }
}

desenharRadar();

const protocolo = location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${protocolo}://${location.host}/ws`);

ws.onmessage = (event) => aplicarEstado(JSON.parse(event.data));

ws.onclose = () => {
  statusEl.textContent = 'desconectado';
  statusEl.className = 'value offline';
};

window.addEventListener('resize', desenharRadar);

const logsInfoEl = document.getElementById('logs-info');
const downloadLogsEl = document.getElementById('download-logs');
const viewLogsBtn = document.getElementById('view-logs');

// Modal elements
const logsModalEl = document.getElementById('logsModal');
const logsViewEl = document.getElementById('logsView');
const logsMetaEl = document.getElementById('logsMeta');
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');

let logsState = { start: 0, lines: 200, total: 0 };

function renderParsedEntries(entries) {
  if (!entries || entries.length === 0) {
    logsViewEl.innerHTML = '<div class="small">Nenhuma entrada de log para mostrar.</div>';
    return;
  }

  let html = '<table class="table table-sm table-striped table-bordered mb-0" style="color:#e6eef8">';
  html += '<thead><tr><th>Timestamp</th><th>Angle</th><th>Distance (cm)</th><th>Temp (°C)</th><th>Portão</th><th>Detecção</th></tr></thead>';
  html += '<tbody>';
  for (const e of entries) {
    const ts = e.timestamp || '-';
    const a = e.angle !== null && e.angle !== undefined ? e.angle.toFixed ? e.angle.toFixed(2) : e.angle : '-';
    const d = e.distance_cm !== null && e.distance_cm !== undefined ? e.distance_cm.toFixed ? e.distance_cm.toFixed(2) : e.distance_cm : '-';
    const t = e.temperature_c !== null && e.temperature_c !== undefined ? e.temperature_c.toFixed ? e.temperature_c.toFixed(2) : e.temperature_c : '-';
    const p = e.portao || '-';
    const det = e.deteccao || '-';
    html += `<tr><td>${ts}</td><td>${a}</td><td>${d}</td><td>${t}</td><td>${p}</td><td>${det}</td></tr>`;
  }
  html += '</tbody></table>';
  logsViewEl.innerHTML = html;
}

async function loadLogsSegment() {
  try {
    const res = await fetch(`/api/logs/parsed?start=${logsState.start}&lines=${logsState.lines}`);
    if (!res.ok) throw new Error('Erro carregando logs');
    const body = await res.json();
    logsState.total = body.total || 0;
    const from = Math.min(logsState.start + 1, logsState.total);
    const to = Math.min(logsState.start + logsState.lines, logsState.total);
    logsMetaEl.textContent = `Mostrando ${from}–${to} de ${logsState.total} linhas`;
    renderParsedEntries(body.entries || []);
  } catch (err) {
    logsViewEl.innerHTML = '<div class="text-danger">Erro carregando logs.</div>';
  }
}

let bsModal = null;
if (window.bootstrap) {
  bsModal = new bootstrap.Modal(logsModalEl);
}

viewLogsBtn?.addEventListener('click', async () => {
  logsState.start = 0;
  await loadLogsSegment();
  if (bsModal) bsModal.show();
});

prevPageBtn?.addEventListener('click', async () => {
  logsState.start = Math.max(0, logsState.start - logsState.lines);
  await loadLogsSegment();
});

nextPageBtn?.addEventListener('click', async () => {
  const next = logsState.start + logsState.lines;
  if (next < logsState.total) {
    logsState.start = next;
    await loadLogsSegment();
  }
});

async function fetchLogsMeta() {
  try {
    const res = await fetch('/api/logs');
    if (!res.ok) throw new Error('Erro ao buscar metadados');
    const meta = await res.json();
    if (!meta.exists) {
      logsInfoEl.textContent = 'Nenhum log disponível.';
      downloadLogsEl.classList.add('disabled');
      downloadLogsEl.setAttribute('aria-disabled', 'true');
    } else {
      const sizeKb = (meta.size_bytes / 1024).toFixed(1);
      logsInfoEl.textContent = `${meta.entries} entradas — ${sizeKb} KB`;
      downloadLogsEl.classList.remove('disabled');
      downloadLogsEl.removeAttribute('aria-disabled');
    }
  } catch (err) {
    logsInfoEl.textContent = 'Erro carregando logs.';
    downloadLogsEl.classList.add('disabled');
    downloadLogsEl.setAttribute('aria-disabled', 'true');
  }
}

fetchLogsMeta();
setInterval(fetchLogsMeta, 5000);