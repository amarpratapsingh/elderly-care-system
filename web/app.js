const els = {
  systemState: document.getElementById('systemState'),
  activitiesCount: document.getElementById('activitiesCount'),
  alertsCount: document.getElementById('alertsCount'),
  voiceCount: document.getElementById('voiceCount'),
  activityBody: document.getElementById('activityBody'),
  alertsBody: document.getElementById('alertsBody'),
  voiceBody: document.getElementById('voiceBody'),
  emergencyResult: document.getElementById('emergencyResult'),
  emergencyBtn: document.getElementById('emergencyBtn'),
  refreshBtn: document.getElementById('refreshBtn'),
  cameraStatus: document.getElementById('cameraStatus'),
  cameraFrame: document.getElementById('cameraFrame'),
};

function formatText(value) {
  return value === null || value === undefined || value === '' ? '-' : String(value);
}

function renderRows(tbody, rows, cols) {
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${cols.length}" class="muted">No data</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map((row) => {
      const tds = cols.map((col) => `<td>${col(row)}</td>`).join('');
      return `<tr>${tds}</tr>`;
    })
    .join('');
}

function severityTag(level) {
  const normalized = formatText(level).toLowerCase();
  return `<span class="tag ${normalized}">${formatText(level)}</span>`;
}

async function fetchJson(url, options = undefined) {
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return await res.json();
}



function refreshCameraFrame() {
  const ts = Date.now();
  els.cameraFrame.src = `/camera-frame?t=${ts}`;
}

async function loadCameraStatus() {
  try {
    const camera = await fetchJson('/api/camera-status');
    if (camera.available) {
      els.cameraStatus.textContent = `Camera active · updated ${formatText(camera.updated_at)}`;
      els.cameraFrame.style.display = 'block';
      refreshCameraFrame();
    } else {
      els.cameraStatus.textContent = 'No camera frame yet. Start main.py to stream frames.';
      els.cameraFrame.style.display = 'none';
      els.cameraFrame.removeAttribute('src');
    }
  } catch (error) {
    els.cameraStatus.textContent = `Camera status unavailable: ${error.message}`;
    els.cameraFrame.style.display = 'none';
  }
}

async function loadDashboard() {
  try {
    const [summary, activity, alerts, voice] = await Promise.all([
      fetchJson('/api/summary'),
      fetchJson('/api/activity?hours=24&limit=20'),
      fetchJson('/api/alerts?hours=72&limit=20'),
      fetchJson('/api/voice?hours=24&limit=20'),
    ]);

    els.systemState.textContent = formatText(summary.runtime?.state);
    els.activitiesCount.textContent = formatText(summary.last_24h?.activities);
    els.alertsCount.textContent = formatText(summary.last_24h?.alerts);
    els.voiceCount.textContent = formatText(summary.last_24h?.voice_commands);

    renderRows(els.activityBody, activity.items || [], [
      (r) => formatText(r.timestamp),
      (r) => formatText(r.activity_type),
      (r) => formatText(r.description),
    ]);

    renderRows(els.alertsBody, alerts.items || [], [
      (r) => formatText(r.timestamp),
      (r) => severityTag(r.severity),
      (r) => formatText(r.alert_type),
      (r) => formatText(r.message),
    ]);

    renderRows(els.voiceBody, voice.items || [], [
      (r) => formatText(r.timestamp),
      (r) => formatText(r.transcript),
      (r) => formatText(r.intent),
      (r) => formatText(r.response),
    ]);

    await loadCameraStatus();
  } catch (error) {
    console.error(error);
    els.emergencyResult.textContent = `Dashboard load failed: ${error.message}`;
  }
}

async function triggerEmergency() {
  els.emergencyBtn.disabled = true;
  els.emergencyResult.textContent = 'Sending emergency alert...';
  try {
    const payload = await fetchJson('/api/emergency', { method: 'POST' });
    if (payload.ok) {
      els.emergencyResult.textContent = `Emergency logged (ID: ${payload.alert_id}).`;
      await loadDashboard();
    } else {
      els.emergencyResult.textContent = 'Failed to log emergency alert.';
    }
  } catch (error) {
    els.emergencyResult.textContent = `Emergency request failed: ${error.message}`;
  } finally {
    els.emergencyBtn.disabled = false;
  }
}

els.refreshBtn.addEventListener('click', () => loadDashboard());
els.emergencyBtn.addEventListener('click', () => triggerEmergency());

loadDashboard();
setInterval(loadDashboard, 5000);


els.cameraFrame.addEventListener('error', () => {
  els.cameraStatus.textContent = 'Camera frame could not be loaded.';
  els.cameraFrame.style.display = 'none';
});
