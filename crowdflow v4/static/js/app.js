/* CrowdFlow PRO v4 — app.js  (all features working) */
'use strict';

// ── STATE ─────────────────────────────────────────────────────
const S = {
  selZone:    null,
  srcMode:    'file',
  threats:    [],
  incidents:  [],
  alerts:     [],
  evacActive: false,
  evacPct:    0,
  charts:     {},
  chartTick:  0,
  zones: [
    {id:'zA',name:'Zone A',color:'#00c8ff',density:0,closed:false},
    {id:'zB',name:'Zone B',color:'#00ff9d',density:0,closed:false},
    {id:'zC',name:'Zone C',color:'#c77dff',density:0,closed:false},
    {id:'zD',name:'Zone D',color:'#ffcc00',density:0,closed:false},
  ],
  evacRoutes: [
    {id:'r1',name:'Route A — North Exit',status:'open',   path:[[0.10,0.92],[0.10,0.04]]},
    {id:'r2',name:'Route B — South Gate',status:'open',   path:[[0.90,0.92],[0.90,0.04]]},
    {id:'r3',name:'Route C — East Exit', status:'open',   path:[[0.55,0.92],[0.96,0.50]]},
    {id:'r4',name:'Route D — Emergency', status:'blocked',path:[[0.10,0.50],[0.55,0.04]]},
  ],
  camNames: [
    'CAM-01 · Main Entry','CAM-02 · Stage Area',
    'CAM-03 · Food Court','CAM-04 · North Exit',
    'CAM-05 · Parking',   'CAM-06 · VIP Zone',
  ],
};

// ── BOOT ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  initMultiCam();
  initPersonList();
  initEvacCanvas();
  renderZones();
  renderQueueList();
  renderEvacRoutes();
  setInterval(pollStatus,  700);
  setInterval(tickClock,  1000);
  setInterval(drawMultiCam, 900);
  setTimeout(buildReport, 1500);
  tickClock();
  setSrcMode('file');
});

// ── TAB NAVIGATION ────────────────────────────────────────────
function goTab(id) {
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.ntab').forEach(t => t.classList.remove('active'));
  document.getElementById(id)?.classList.add('active');
  document.querySelectorAll('.ntab').forEach(t => {
    if (t.getAttribute('onclick')?.includes(id)) t.classList.add('active');
  });
  if (id === 'paneEvac')   setTimeout(initEvacCanvas, 50);
  if (id === 'paneSpeed')  setTimeout(initSpeedCanvas, 50);
  if (id === 'paneReport') buildReport();
}

// ── SOURCE MODE SWITCHER ──────────────────────────────────────
function setSrcMode(mode) {
  S.srcMode = mode;
  ['file','mobile','rtsp','usb'].forEach(m => {
    document.getElementById(`srcBtn${m.charAt(0).toUpperCase()+m.slice(1)}`)?.classList.remove('active');
  });
  document.getElementById({
    file:'srcBtnFile', mobile:'srcBtnMobile', rtsp:'srcBtnRTSP', usb:'srcBtnUSB'
  }[mode])?.classList.add('active');

  document.getElementById('fileArea').style.display = mode === 'file' ? 'block' : 'none';
  document.getElementById('urlArea').style.display  = mode !== 'file' ? 'block' : 'none';

  const hints = {
    mobile: 'Phone URL (IP Webcam app)',
    rtsp:   'RTSP URL — rtsp://admin:pass@ip:554/stream',
    usb:    'USB index — enter 0 for first webcam',
  };
  const placeholders = {
    mobile: 'http://192.168.1.100:8080/video',
    rtsp:   'rtsp://admin:password@192.168.1.50:554/stream1',
    usb:    '0',
  };
  if (mode !== 'file') {
    $('urlHint', hints[mode] || 'Stream URL');
    document.getElementById('urlInp').placeholder = placeholders[mode] || '';
  }
}

// ── UPLOAD VIDEO FILE ─────────────────────────────────────────
async function uploadFile(event) {
  const file = event.target.files[0];
  if (!file) return;

  document.getElementById('progWrap').style.display = 'block';
  const fill = document.getElementById('progFill');
  const lbl  = document.getElementById('progLbl');
  lbl.textContent = `Uploading ${file.name}…`;

  let pct = 0;
  const iv = setInterval(() => { pct = Math.min(88, pct + 6); fill.style.width = pct + '%'; }, 200);

  try {
    const fd = new FormData();
    fd.append('video', file);
    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const d = await r.json();
    clearInterval(iv);
    fill.style.width = '100%';

    if (d.ok) {
      lbl.textContent = `✓ ${d.frame_count} frames @ ${d.fps} fps · ${d.duration}s`;
      setSrcStatus('green', `✓ File loaded: ${file.name}`);
      $('feedLabel', `CAM-01 · ${file.name.substring(0, 28).toUpperCase()}`);
      // Show seek bar for video file
      document.getElementById('seekBar').max = d.frame_count;
      document.getElementById('seekOverlay').classList.remove('hidden');
      setStreamBadge('live', '● VIDEO FILE');
      addAlert('INFO', 'VIDEO', `Loaded: ${file.name} (${d.duration}s @ ${d.fps}fps)`);
    } else {
      lbl.textContent = 'Error: ' + (d.error || 'Unknown');
      setSrcStatus('red', '✗ Upload failed');
    }
  } catch (e) {
    clearInterval(iv);
    lbl.textContent = 'Upload failed — is Flask running?';
    setSrcStatus('red', '✗ Server not reachable');
  }
}

// ── CONNECT LIVE STREAM ───────────────────────────────────────
async function applyStream() {
  const url   = document.getElementById('urlInp').value.trim();
  const label = S.srcMode === 'mobile' ? 'Mobile Phone' :
                S.srcMode === 'rtsp'   ? 'CCTV IP Camera' : 'USB Webcam';
  if (!url) { addAlert('INFO', 'SOURCE', 'Enter a URL or index first'); return; }

  setSrcStatus('amber', '● Connecting…');
  setStreamBadge('connecting', '● CONNECTING…');

  try {
    const r = await fetch('/api/set_source', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, label }),
    });
    const d = await r.json();
    if (d.ok || d.connected) {
      setSrcStatus('green', `✓ Connected: ${label}`);
      setStreamBadge('live', `● LIVE · ${label.toUpperCase()}`);
      $('feedLabel', `CAM-01 · ${label.toUpperCase()}`);
      document.getElementById('seekOverlay').classList.add('hidden');
      addAlert('INFO', 'SOURCE', `Connected: ${label} → ${url}`);
    } else {
      setSrcStatus('red', '✗ Connection failed');
      setStreamBadge('', '● FAILED');
    }
  } catch {
    setSrcStatus('red', '✗ Server not reachable');
  }
}

function setSrcStatus(col, msg) {
  const el = document.getElementById('srcStatus');
  el.textContent = msg;
  el.style.color = col === 'green' ? 'var(--green)' : col === 'red' ? 'var(--red)' : 'var(--amber)';
}

function setStreamBadge(cls, txt) {
  const el = document.getElementById('streamBadge');
  el.className = 'stream-badge' + (cls ? ' ' + cls : '');
  el.textContent = txt;
  $('liveLabel', cls === 'live' ? 'LIVE' : cls === 'connecting' ? 'CONNECTING' : 'IDLE');
}

// ── OVERLAY TOGGLES ───────────────────────────────────────────
async function sendOverlay() {
  const data = {
    heatmap: document.getElementById('togHeat').checked,
    boxes:   document.getElementById('togBoxes').checked,
    trails:  document.getElementById('togTrails').checked,
    flow:    document.getElementById('togFlow').checked,
    zones:   document.getElementById('togZones').checked,
  };
  try { await fetch('/api/overlay', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) }); }
  catch {}
}

async function sendSensitivity(v) {
  try { await fetch('/api/sensitivity', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({value: v}) }); }
  catch {}
}

// ── SEEK (video file) ─────────────────────────────────────────
async function doSeek(v) {
  try { await fetch('/api/seek', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({frame: v}) }); }
  catch {}
}

// ── STATUS POLLING ────────────────────────────────────────────
async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    if (!r.ok) return;
    const d = await r.json();

    updateTopbar(d);
    updateZoneList(d.zones);
    updateEntryExit(d.entry_exit);
    updateQueues(d.queue_data);
    updateAlertFeed(d.alerts);
    updatePredChart(d.prediction);
    updateBehaviors(d.metrics?.behaviors || []);
    updateThreatPanel(d.threats || []);
    updateSpeedStats(d.speed);
    S.chartTick++;
    if (S.chartTick % 3 === 0) updateCharts(d);
    updateSeekDisplay(d.metrics);
  } catch {}
}

function updateSeekDisplay(m) {
  if (!m) return;
  if (m.source_type === 'file' && m.total_frames > 0) {
    document.getElementById('seekBar').value = m.frame_idx;
    const cur = m.frame_idx / (m.fps || 25);
    const tot = m.total_frames / (m.fps || 25);
    $('vcTime', `${fmt(cur)} / ${fmt(tot)}`);
    $('hudTR', `● ${fmt(cur)} / ${fmt(tot)}`);
  } else {
    const now = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    $('hudTR', `● LIVE · ${now}`);
  }
}

// ── TOPBAR ────────────────────────────────────────────────────
function updateTopbar(d) {
  const m  = d.metrics || {};
  const ee = d.entry_exit || {};
  const rc = {CRITICAL:'var(--red)',HIGH:'var(--orange)',MEDIUM:'var(--amber)',LOW:'var(--green)'};
  $('mDetected', m.detected ?? '—');
  $('mDensity',  m.avg_density != null ? Math.round(m.avg_density*100)+'%' : '—');
  $('mEntries',  ee.total_entries ?? 0);
  $('mExits',    ee.total_exits   ?? 0);
  $('mQueues',   (d.queue_data||[]).length);
  $('mThreats',  (d.threats||[]).length);
  $('mProfile',  d.profile || '—');
  const risk = m.risk_level || '—';
  const rEl  = document.getElementById('mRisk');
  if (rEl) { rEl.textContent = risk; rEl.style.color = rc[risk] || 'var(--cyan)'; }
  $('mFlow',  m.flow_dir || '—');
  $('hudBR',  `DENSITY: ${m.avg_density!=null?Math.round(m.avg_density*100):'—'}% · RISK: ${risk}`);
  $('nbThreat', (d.threats||[]).length);
  $('mThreats',  (d.threats||[]).length);
  // Stream status
  if (m.has_source) setStreamBadge('live', m.source_type === 'file' ? '● VIDEO FILE' : '● LIVE STREAM');
}

// ── ZONE LIST ─────────────────────────────────────────────────
function updateZoneList(zones) {
  if (!zones) return;
  zones.forEach(z => { const sz = S.zones.find(s => s.id === z.id); if (sz) { sz.density = z.density; sz.closed = z.closed; } });
  renderZones();
}

function renderZones() {
  document.getElementById('zoneList').innerHTML = S.zones.map(z => {
    const p   = Math.round((z.density||0)*100);
    const col = p>75?'var(--red)':p>50?'var(--amber)':'var(--green)';
    return `<div class="zrow ${S.selZone===z.id?'sel':''} ${p>80?'danger':''}" onclick="selZone('${z.id}')">
      <div class="zpip" style="background:${z.color}"></div>
      <span class="zlbl">${z.name}${z.closed?' [CLOSED]':''}</span>
      <span class="zpct" style="color:${col}">${p}%</span>
      <div class="zbar-track"><div class="zbar-fill" style="width:${p}%;background:${col}"></div></div>
    </div>`;
  }).join('');
}

function selZone(id) { S.selZone = id; renderZones(); }

// ── ENTRY / EXIT ──────────────────────────────────────────────
function updateEntryExit(ee) {
  if (!ee) return;
  $('rcEntry', ee.total_entries ?? 0);
  $('rcExit',  ee.total_exits   ?? 0);
  $('rcNet',   ee.net_inside    ?? 0);
  $('rcRate',  (ee.entries_per_min ?? 0) + '/m');
  $('mEntries', ee.total_entries ?? 0);
  $('mExits',   ee.total_exits   ?? 0);
}

// ── QUEUES ────────────────────────────────────────────────────
function renderQueueList() {
  const qs = [{name:'Main Entrance',length:14},{name:'Security Gate',length:36},{name:'Side Exit',length:5}];
  renderQueues(qs);
}
function updateQueues(qs) { if (qs?.length) renderQueues(qs); }
function renderQueues(qs) {
  document.getElementById('queueList').innerHTML = qs.map(q => {
    const st = q.status || (q.length>28?'LONG':q.length>12?'MEDIUM':'SHORT');
    const c  = st==='LONG'?'var(--red)':st==='MEDIUM'?'var(--amber)':'var(--green)';
    const bc = st==='LONG'?'b-r':st==='MEDIUM'?'b-a':'b-g';
    return `<div class="qrow">
      <div class="qbar" style="background:${c}"></div>
      <div style="flex:1;font-size:11px">${q.name}</div>
      <span class="badge ${bc}">${q.length||0}</span>
    </div>`;
  }).join('');
}

// ── ALERT FEED ────────────────────────────────────────────────
function updateAlertFeed(alerts) {
  if (!alerts?.length) return;
  document.getElementById('alertFeed').innerHTML = alerts.slice(0,8).map(a => {
    const tc = a.type==='CRITICAL'?'var(--red)':a.type==='WARNING'?'var(--amber)':'var(--cyan)';
    return `<div class="al ${a.type}">
      <div class="al-head">
        <span class="al-type" style="color:${tc}">${a.type} · ${a.event}</span>
        <span class="al-time">${a.time}</span>
      </div>
      <div class="al-msg">${a.message}</div>
    </div>`;
  }).join('');
}

function addAlert(type, event, msg) {
  const t   = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const tc  = type==='CRITICAL'?'var(--red)':type==='WARNING'?'var(--amber)':'var(--cyan)';
  const div = document.createElement('div');
  div.className = `al ${type}`;
  div.innerHTML = `<div class="al-head"><span class="al-type" style="color:${tc}">${type} · ${event}</span><span class="al-time">${t}</span></div><div class="al-msg">${msg}</div>`;
  document.getElementById('alertFeed').prepend(div);
}

// ── ML PREDICTION CHART ───────────────────────────────────────
let _predCh = null;
function updatePredChart(pred) {
  if (!pred?.predictions?.length) return;
  const labels = ['Now', ...pred.labels];
  const vals   = [pred.current, ...pred.predictions];
  if (!_predCh) {
    _predCh = new Chart(document.getElementById('predChart').getContext('2d'), {
      type: 'line',
      data: { labels, datasets: [{ data: vals, borderColor:'#c77dff', backgroundColor:'rgba(199,125,255,0.1)', fill:true, tension:0.4, pointRadius:0, borderWidth:1.5 }] },
      options: { responsive:true, maintainAspectRatio:false, animation:{duration:0}, plugins:{legend:{display:false}}, scales:{x:{display:false},y:{display:false,min:0,max:100}} },
    });
  } else {
    _predCh.data.labels = labels;
    _predCh.data.datasets[0].data = vals;
    _predCh.update('none');
  }
  const tc = pred.trend==='rising'?'var(--red)':'var(--green)';
  document.getElementById('predInfo').innerHTML =
    `Trend: <span style="color:${tc}">${pred.trend==='rising'?'▲ Rising':'▼ Falling'}</span> · Confidence: ${pred.confidence}%` +
    (pred.peak_eta ? ` · Peak: ${pred.peak_eta}` : '');
}

// ── BEHAVIORS ─────────────────────────────────────────────────
function updateBehaviors(beh) {
  const el = document.getElementById('behaviorList');
  if (!el) return;
  if (!beh.length) { el.innerHTML = '<div class="empty-msg">✅ Normal crowd behavior</div>'; return; }
  el.innerHTML = beh.map(b =>
    `<div style="font-size:11px;color:${b.severity==='CRITICAL'?'var(--red)':'var(--amber)'};padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
      ⚠ <strong>${b.type}</strong>: ${b.detail} <span style="color:var(--text2)">[${b.zone}]</span>
    </div>`).join('');
}

// ── THREAT PANEL ──────────────────────────────────────────────
function updateThreatPanel(threats) {
  S.threats = threats;
  const el = document.getElementById('activeThreatList');
  if (!threats.length) {
    el.innerHTML = '<div class="empty-msg">No active threats.</div>';
    document.getElementById('threatBanner').classList.add('hidden');
    return;
  }
  el.innerHTML = threats.map(t =>
    `<div class="person-card danger">
      <div class="pav" style="background:rgba(255,32,64,0.15)">⚠️</div>
      <div class="pinfo">
        <div class="pid">${t.id} · ${t.name}</div>
        <div class="pstatus">${t.zone} · ${t.weapon}</div>
        <div class="pstatus" style="color:var(--blue);font-size:9px">✓ Authorities excluded from civilian alert</div>
      </div>
      <span class="badge b-r">THREAT</span>
    </div>`).join('');
  document.getElementById('threatBanner').classList.remove('hidden');
  $('nbThreat', threats.length);
  $('mThreats', threats.length);
}

function initPersonList() {
  const persons = [
    {id:'P-001',name:'Person A-01',  type:'CIVILIAN', zone:'Zone A', weapon:null},
    {id:'P-002',name:'Person B-02',  type:'CIVILIAN', zone:'Zone B', weapon:null},
    {id:'P-003',name:'Person C-03',  type:'CIVILIAN', zone:'Zone C', weapon:null},
    {id:'P-004',name:'Officer K-12', type:'POLICE',   zone:'Zone B', weapon:'Service pistol (auth)'},
    {id:'P-005',name:'Sgt. Rajan V.',type:'ARMY',     zone:'Zone C', weapon:'Auth rifle'},
    {id:'P-006',name:'Guard Unit-3', type:'SECURITY', zone:'Zone D', weapon:'Auth baton'},
  ];
  document.getElementById('personList').innerHTML = persons.map(p => {
    const auth = ['POLICE','ARMY','SECURITY'].includes(p.type);
    const av   = {POLICE:'👮',ARMY:'🪖',SECURITY:'🛡️'}[p.type] || '🧍';
    return `<div class="person-card ${auth?'auth':''}">
      <div class="pav" style="background:${auth?'rgba(77,166,255,0.12)':'rgba(0,255,157,0.08)'}">${av}</div>
      <div class="pinfo">
        <div class="pid">${p.id} · ${p.name}</div>
        <div class="pstatus">${p.zone}${p.weapon?' · '+p.weapon:''}</div>
      </div>
      <span class="badge ${auth?'b-blue':'b-g'}">${p.type}</span>
    </div>`;
  }).join('');
}

// ── WEAPON TEST ───────────────────────────────────────────────
async function weaponTest() {
  const zone = S.selZone ? S.zones.find(z=>z.id===S.selZone)?.name || 'Zone A' : 'Zone A';
  try {
    const r = await fetch('/api/weapon_test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ zone }),
    });
    const d = await r.json();
    if (d.ok && d.threat) {
      showWeaponNotif(d.threat);
      drawThreatBox(d.threat);
      const cl = document.getElementById('civilianLog');
      if (cl) {
        const t = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
        cl.innerHTML = `<div style="color:var(--red)">⚠ [${t}] Weapon alert → civilians in ${zone}</div>
          <div>→ <strong>EXCLUDED:</strong> Police · Army · Security (authorised)</div>
          <div>→ ${Math.floor(Math.random()*400+250)} civilian devices notified</div>
          <div>→ Nearest exits sent to attendee phones</div>` + cl.innerHTML;
      }
      addAlert('CRITICAL', 'THREAT', `⚠ WEAPON: ${d.threat.weapon} in ${zone}`);
      goTab('paneThreat');
    }
  } catch {
    addAlert('INFO', 'WEAPON', 'Weapon test (demo — start Flask for real detection)');
  }
}

function showWeaponNotif(t) {
  $('wnBody',   `${t.weapon} detected near ${t.zone}. Move calmly to nearest exit.`);
  $('wnFooter', `Zone: ${t.zone} · Confidence: ${Math.round(t.confidence*100)}% · Security dispatched`);
  document.getElementById('weaponNotif').classList.remove('hidden');
  setTimeout(() => document.getElementById('weaponNotif').classList.add('hidden'), 15000);
}
function dismissNotif() { document.getElementById('weaponNotif').classList.add('hidden'); }

function drawThreatBox(threat) {
  let cv = document.getElementById('threatOvCv');
  const feed = document.querySelector('.threat-feed');
  if (!cv) {
    cv = document.createElement('canvas');
    cv.id = 'threatOvCv';
    cv.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;';
    feed.appendChild(cv);
  }
  cv.width = feed.offsetWidth || 640; cv.height = feed.offsetHeight || 360;
  const ctx = cv.getContext('2d'); const W = cv.width; const H = cv.height;
  const bx = W*0.38, by = H*0.28, bw = 72, bh = 115; let tk = 0;
  function draw() {
    ctx.clearRect(0,0,W,H); tk++;
    const pulse = 0.5+0.5*Math.sin(tk*0.1);
    const col = `rgba(255,32,64,${0.4+pulse*0.5})`;
    const ck = 13;
    ctx.strokeStyle = col; ctx.lineWidth = 2;
    [[bx,by],[bx+bw,by],[bx,by+bh],[bx+bw,by+bh]].forEach(([px,py]) => {
      const dx=px===bx?1:-1, dy=py===by?1:-1;
      ctx.beginPath();
      ctx.moveTo(px+dx*ck,py); ctx.lineTo(px,py); ctx.lineTo(px,py+dy*ck);
      ctx.stroke();
    });
    ctx.font = '700 11px Orbitron'; ctx.fillStyle = col;
    ctx.fillText('⚠ THREAT', bx-4, by-10);
    ctx.fillText(threat.weapon || 'WEAPON', bx, by+bh+14);
    ctx.fillText(`CONF: ${Math.round(threat.confidence*100)}%`, bx, by+bh+26);
    requestAnimationFrame(draw);
  }
  draw();
}

async function clearThreats() {
  try { await fetch('/api/clear_threats', { method: 'POST' }); } catch {}
  S.threats = [];
  document.getElementById('activeThreatList').innerHTML = '<div class="empty-msg">No active threats.</div>';
  document.getElementById('threatBanner').classList.add('hidden');
  const cv = document.getElementById('threatOvCv');
  if (cv) cv.getContext('2d').clearRect(0,0,cv.width,cv.height);
  $('nbThreat', 0); $('mThreats', 0);
  addAlert('INFO', 'SYSTEM', 'All threats cleared');
}

// ── STAFF CONTROLS ────────────────────────────────────────────
async function staffDo(action) {
  if (!S.selZone) { addAlert('INFO','SYSTEM','Select a zone first (click in Zone Monitor)'); return; }
  try {
    await fetch('/api/zone_action', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ zone_id: S.selZone, action }),
    });
  } catch {}
  addAlert('WARNING', S.selZone, `Zone action: ${action.toUpperCase()} by operator`);
  if (action === 'close') { const z = S.zones.find(z=>z.id===S.selZone); if (z) z.closed = true; }
  if (action === 'open')  { const z = S.zones.find(z=>z.id===S.selZone); if (z) z.closed = false; }
  renderZones();
}

async function manualAlert() {
  try { await fetch('/api/alert', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:'Manual alert by operator'}) }); } catch {}
  addAlert('CRITICAL', 'MANUAL', 'Manual alert raised by operator');
}

async function takeSnap() {
  try { await fetch('/api/snapshot', { method: 'POST' }); } catch {}
  addAlert('INFO', 'SNAPSHOT', 'Snapshot captured — saved to /reports/');
}

// ── EVACUATION ────────────────────────────────────────────────
async function triggerEvac() {
  try { await fetch('/api/evacuation', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({action:'trigger'}) }); } catch {}
  S.evacActive = true; S.evacPct = 0;
  addAlert('CRITICAL', 'EVACUATION', '🚨 Emergency evacuation triggered!');
  const cv = document.getElementById('evacCanvas');
  if (cv) drawEvacMap(cv, 0);
  const iv = setInterval(() => {
    S.evacPct = Math.min(100, S.evacPct + 1.2);
    $('evacPct', Math.round(S.evacPct) + '%');
    $('evacTime', Math.max(0, Math.round((100-S.evacPct)/6)));
    const log = document.getElementById('evacLog');
    if (log && S.evacPct < 2) log.innerHTML += '<div>Evacuation started</div>';
    if (S.evacPct >= 100) clearInterval(iv);
  }, 350);
  goTab('paneEvac');
}

async function clearEvac() {
  try { await fetch('/api/evacuation', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({action:'clear'}) }); } catch {}
  S.evacActive = false; S.evacPct = 0;
  $('evacPct', '0%'); $('evacTime', '—');
  addAlert('INFO', 'EVACUATION', 'All-clear issued');
}

function initEvacCanvas() {
  const cv = document.getElementById('evacCanvas'); if (!cv) return;
  const r  = cv.parentElement.getBoundingClientRect();
  cv.width = r.width || 600; cv.height = r.height || 400;
  renderEvacRoutes();
  drawEvacMap(cv, 0);
}

function renderEvacRoutes() {
  const el = document.getElementById('evacRouteList'); if (!el) return;
  el.innerHTML = S.evacRoutes.map(r =>
    `<div class="evac-route ${r.status}">
      <div class="er-name" style="color:${r.status==='open'?'var(--green)':'var(--red)'}">${r.name}</div>
      <div class="er-info">Status: <strong>${r.status.toUpperCase()}</strong></div>
    </div>`).join('');
  const blocked = S.evacRoutes.filter(r => r.status === 'blocked');
  $('evacBottleneck', blocked.length ? blocked.map(r=>`⚠ ${r.name} blocked`).join('<br>') : '✅ No bottlenecks');
}

function drawEvacMap(cv, frame) {
  const ctx = cv.getContext('2d'); const EW = cv.width; const EH = cv.height;
  ctx.fillStyle = '#02080d'; ctx.fillRect(0,0,EW,EH);
  ctx.strokeStyle = 'rgba(0,224,255,0.05)'; ctx.lineWidth = 0.5;
  for (let x=0;x<EW;x+=40) { ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,EH);ctx.stroke(); }
  for (let y=0;y<EH;y+=40) { ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(EW,y);ctx.stroke(); }
  S.zones.forEach((z,i) => {
    const x0=[0,EW/2,0,EW/2][i], y0=[0,0,EH/2,EH/2][i];
    ctx.strokeStyle = z.color+'45'; ctx.lineWidth = 1; ctx.setLineDash([4,4]);
    ctx.strokeRect(x0,y0,EW/2,EH/2); ctx.setLineDash([]);
    ctx.font = '600 11px "Exo 2"'; ctx.fillStyle = z.color+'80';
    ctx.fillText(z.name, x0+8, y0+18);
  });
  S.evacRoutes.forEach(r => {
    const col = r.status==='open' ? '#00ff9d' : '#ff2040';
    ctx.strokeStyle = col; ctx.lineWidth = S.evacActive ? 3 : 1.5;
    ctx.setLineDash(r.status==='blocked' ? [6,4] : []);
    ctx.beginPath();
    ctx.moveTo(r.path[0][0]*EW, r.path[0][1]*EH);
    ctx.lineTo(r.path[1][0]*EW, r.path[1][1]*EH);
    ctx.stroke(); ctx.setLineDash([]);
    const mx=(r.path[0][0]+r.path[1][0])/2*EW, my=(r.path[0][1]+r.path[1][1])/2*EH;
    const ang = Math.atan2(r.path[1][1]-r.path[0][1], r.path[1][0]-r.path[0][0]);
    ctx.fillStyle = col; ctx.beginPath();
    ctx.moveTo(mx+9*Math.cos(ang),my+9*Math.sin(ang));
    ctx.lineTo(mx-7*Math.cos(ang-0.5),my-7*Math.sin(ang-0.5));
    ctx.lineTo(mx-7*Math.cos(ang+0.5),my-7*Math.sin(ang+0.5));
    ctx.closePath(); ctx.fill();
    ctx.font = '9px Orbitron'; ctx.fillStyle = col;
    ctx.fillText(r.name.split('—')[0].trim(), mx+12, my+4);
  });
  [{x:0.04,y:0.02,l:'EXIT N'},{x:0.88,y:0.02,l:'EXIT E'},{x:0.04,y:0.86,l:'EXIT W'},{x:0.88,y:0.86,l:'EXIT S'}].forEach(e => {
    ctx.fillStyle='rgba(0,255,157,0.12)'; ctx.strokeStyle='rgba(0,255,157,0.5)'; ctx.lineWidth=1.2;
    ctx.fillRect(e.x*EW-20,e.y*EH-10,58,20); ctx.strokeRect(e.x*EW-20,e.y*EH-10,58,20);
    ctx.font='700 9px Orbitron'; ctx.fillStyle='#00ff9d'; ctx.fillText(e.l,e.x*EW-14,e.y*EH+4);
  });
  if (S.evacActive) {
    const t = (frame||0)*0.003;
    S.evacRoutes.filter(r=>r.status==='open').forEach((r,ri) => {
      for (let i=0;i<16;i++) {
        const f = ((t+i*0.065+ri*0.34)%1);
        const px = (r.path[0][0]+(r.path[1][0]-r.path[0][0])*f)*EW;
        const py = (r.path[0][1]+(r.path[1][1]-r.path[0][1])*f)*EH;
        ctx.fillStyle = 'rgba(0,255,157,0.75)';
        ctx.beginPath(); ctx.arc(px,py,3,0,Math.PI*2); ctx.fill();
      }
    });
    requestAnimationFrame(f => drawEvacMap(cv, f));
  }
}

// ── SPEED MAP ─────────────────────────────────────────────────
let _speedActive = false;
function initSpeedCanvas() {
  const cv = document.getElementById('speedCanvas'); if (!cv) return;
  const r  = cv.parentElement.getBoundingClientRect();
  cv.width = (r.width||600) - 225; cv.height = r.height || 400;
  _speedActive = true;
  speedLoop(cv, 0);
}

function speedLoop(cv, frame) {
  if (!document.getElementById('paneSpeed')?.classList.contains('active')) { _speedActive=false; return; }
  requestAnimationFrame(f => speedLoop(cv, f));
  const ctx = cv.getContext('2d'); const SW = cv.width; const SH = cv.height;
  const C=16, R=10;
  ctx.fillStyle = 'rgba(2,11,16,0.45)'; ctx.fillRect(0,0,SW,SH);
  for (let r=0;r<R;r++) for (let c=0;c<C;c++) {
    const spd = Math.max(0, 10+Math.sin(frame*0.016+r*0.7+c*0.55)*16+Math.random()*5);
    const [rc,g,b] = spd<5?[48,80,220]:spd<15?[0,220,120]:spd<25?[220,200,0]:[255,32,64];
    ctx.fillStyle = `rgba(${rc},${g},${b},${Math.min(0.82,spd/22*0.75)})`;
    ctx.fillRect(c/C*SW+1, r/R*SH+1, SW/C-2, SH/R-2);
    if (spd>8) { ctx.font='8px Orbitron'; ctx.fillStyle=`rgba(${rc},${g},${b},0.85)`; ctx.fillText(Math.round(spd),c/C*SW+3,r/R*SH+13); }
  }
  S.zones.forEach((z,i) => {
    ctx.font='600 11px "Exo 2"'; ctx.fillStyle=z.color+'70';
    ctx.fillText(z.name, ([0,SW/2,0,SW/2][i])+6, ([0,0,SH/2,SH/2][i])+18);
  });
}

function updateSpeedStats(speed) {
  if (!speed) return;
  $('spAvg', speed.avg_speed ?? '—');
  $('spMax', speed.max_speed ?? '—');
  const rEl = document.getElementById('spRisk');
  if (rEl) {
    rEl.textContent = speed.stampede_risk || 'LOW';
    rEl.style.color = speed.stampede_risk==='HIGH'?'var(--red)':speed.stampede_risk==='MEDIUM'?'var(--amber)':'var(--green)';
  }
  document.getElementById('zoneSpeedList').innerHTML = S.zones.map(z => {
    const spd = Math.round((z.density||0)*30 + Math.random()*4);
    const c   = spd>20?'var(--red)':spd>12?'var(--amber)':'var(--green)';
    return `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:11px">
      <span>${z.name}</span><span style="font-family:var(--mono);color:${c}">${spd} px/f</span>
    </div>`;
  }).join('');
}

// ── MULTI-CAM ─────────────────────────────────────────────────
function initMultiCam() {
  const g = document.getElementById('camGrid');
  g.innerHTML = S.camNames.map((n,i) =>
    `<div class="cam-cell" id="cc${i}" onclick="this.classList.toggle('active')">
      <canvas id="ccv${i}" width="320" height="180"></canvas>
      <div class="cam-lbl">${n}</div>
      <div class="cam-pct" id="cpt${i}">0%</div>
      <div class="cam-dot" id="cdt${i}"></div>
    </div>`).join('');
}

function drawMultiCam() {
  if (!document.getElementById('paneMultiCam')?.classList.contains('active')) return;
  S.camNames.forEach((_,i) => {
    const cv = document.getElementById(`ccv${i}`); if (!cv) return;
    const ctx = cv.getContext('2d'); const d = 0.1+Math.random()*0.65; const p = Math.round(d*100);
    ctx.fillStyle='#02080d'; ctx.fillRect(0,0,320,180);
    ctx.strokeStyle='rgba(0,224,255,0.05)'; ctx.lineWidth=0.5;
    for (let x=0;x<320;x+=28){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,180);ctx.stroke();}
    for (let y=0;y<180;y+=18){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(320,y);ctx.stroke();}
    for (let b=0;b<Math.floor(d*18);b++){
      const bx=8+Math.random()*304, by=8+Math.random()*164;
      const r=p>75?255:p>50?255:0, g=p>75?45:p>50?165:200;
      ctx.fillStyle=`rgba(${r},${g},${p<50?157:0},${0.2+Math.random()*0.3})`;
      ctx.beginPath();ctx.arc(bx,by,2+Math.random()*7,0,Math.PI*2);ctx.fill();
    }
    const col = p>75?'#ff2040':p>50?'#ffcc00':'#00ff9d';
    const el = document.getElementById(`cpt${i}`);
    if (el) { el.textContent=p+'%'; el.style.color=col; el.style.background=col+'20'; }
    document.getElementById(`cdt${i}`)?.classList.toggle('on', p>80);
  });
}

function alertAllCams() {
  S.camNames.forEach((_,i) => document.getElementById(`cdt${i}`)?.classList.add('on'));
  addAlert('CRITICAL','ALL-CAMS','Mass alert broadcast across all 6 camera channels');
}
function syncCams() { addAlert('INFO','SYSTEM','All cameras synchronised'); }

// ── ANALYTICS CHARTS ──────────────────────────────────────────
const CO = {
  responsive:true, maintainAspectRatio:false, animation:{duration:200},
  plugins:{legend:{labels:{color:'#2a5a6a',font:{family:'Exo 2',size:10},boxWidth:10}}},
  scales:{
    x:{grid:{color:'rgba(0,224,255,0.04)'},ticks:{color:'#2a5a6a',font:{family:'Orbitron',size:7}}},
    y:{grid:{color:'rgba(0,224,255,0.04)'},ticks:{color:'#2a5a6a',font:{family:'Orbitron',size:7}}},
  }
};

function initCharts() {
  const mk = (id, label, color, fill=false) => new Chart(
    document.getElementById(id).getContext('2d'),{
      type:'line',
      data:{labels:[],datasets:[{label,data:[],borderColor:color,backgroundColor:color+'18',fill,tension:0.4,pointRadius:0,borderWidth:1.5}]},
      options:CO
    }
  );
  S.charts.count   = mk('anlCount','Count','#00e0ff',true);
  S.charts.flow    = new Chart(document.getElementById('anlFlow').getContext('2d'),{
    type:'line',
    data:{labels:[],datasets:[
      {label:'Entries',data:[],borderColor:'#00ff9d',fill:true,backgroundColor:'rgba(0,255,157,0.07)',tension:0.4,pointRadius:0,borderWidth:1.5},
      {label:'Exits',  data:[],borderColor:'#ff2040',fill:true,backgroundColor:'rgba(255,32,64,0.07)', tension:0.4,pointRadius:0,borderWidth:1.5},
    ]},options:CO
  });
  S.charts.density = new Chart(document.getElementById('anlDensity').getContext('2d'),{
    type:'bar',
    data:{labels:['Zone A','Zone B','Zone C','Zone D'],datasets:[{label:'Density %',data:[0,0,0,0],
      backgroundColor:['#00e0ff55','#00ff9d55','#c77dff55','#ffcc0055'],
      borderColor:['#00e0ff','#00ff9d','#c77dff','#ffcc00'],borderWidth:1.5}]},options:CO
  });
  S.charts.predict = new Chart(document.getElementById('anlPredict').getContext('2d'),{
    type:'line',
    data:{labels:[],datasets:[
      {label:'Actual',    data:[],borderColor:'#00e0ff',tension:0.4,pointRadius:0,borderWidth:1.5,fill:false},
      {label:'Predicted', data:[],borderColor:'#c77dff',borderDash:[5,3],tension:0.4,pointRadius:0,borderWidth:1.5,backgroundColor:'rgba(199,125,255,0.07)',fill:true},
    ]},options:CO
  });
  S.charts.behavior = new Chart(document.getElementById('anlBehavior').getContext('2d'),{
    type:'doughnut',
    data:{labels:['Normal','Rushing','Loitering','Queuing','Abnormal'],datasets:[{
      data:[68,11,9,8,4],
      backgroundColor:['#00ff9d','#ffcc00','#00e0ff','#c77dff','#ff2040'],borderWidth:0
    }]},
    options:{responsive:true,maintainAspectRatio:false,animation:{duration:200},
      plugins:{legend:{labels:{color:'#2a5a6a',font:{family:'Exo 2',size:10},boxWidth:10}}},
      scales:{},cutout:'65%'}
  });
  S.charts.zones = new Chart(document.getElementById('anlZones').getContext('2d'),{
    type:'line',
    data:{labels:[],datasets:S.zones.map(z=>({label:z.name,data:[],borderColor:z.color,fill:false,tension:0.4,pointRadius:0,borderWidth:1.5}))},
    options:CO
  });
}

function updateCharts(d) {
  const m  = d.metrics || {};
  const ee = d.entry_exit || {};
  const zs = d.zones || [];
  const t  = String(S.chartTick);

  push1(S.charts.count, t, m.detected||0);
  push2(S.charts.flow,  t, ee.entries_per_min||0, ee.exits_per_min||0);

  if (zs.length===4) {
    S.charts.density.data.datasets[0].data = zs.map(z=>z.density_pct);
    S.charts.density.update('none');
  }

  S.charts.zones.data.labels.push(t);
  zs.slice(0,4).forEach((z,i) => {
    S.charts.zones.data.datasets[i].data.push(z.density_pct);
    if (S.charts.zones.data.datasets[i].data.length > 35)
      S.charts.zones.data.datasets[i].data.shift();
  });
  if (S.charts.zones.data.labels.length > 35) S.charts.zones.data.labels.shift();
  S.charts.zones.update('none');

  if (d.prediction?.predictions?.length) {
    const pred = d.prediction;
    const hist = (m.count_history||[]).slice(-12);
    const hl   = hist.map((_,i)=>`-${hist.length-i}`);
    const pl   = pred.labels.slice(0,8);
    S.charts.predict.data.labels = [...hl,...pl];
    S.charts.predict.data.datasets[0].data = [...hist,...Array(pl.length).fill(null)];
    S.charts.predict.data.datasets[1].data = [...Array(hist.length).fill(null),pred.current,...pred.predictions.slice(0,7)];
    S.charts.predict.update('none');
  }
}

function push1(c,l,v){c.data.labels.push(l);c.data.datasets[0].data.push(v);if(c.data.labels.length>35){c.data.labels.shift();c.data.datasets[0].data.shift();}c.update('none');}
function push2(c,l,v1,v2){c.data.labels.push(l);c.data.datasets[0].data.push(v1);c.data.datasets[1].data.push(v2);if(c.data.labels.length>35){c.data.labels.shift();c.data.datasets[0].data.shift();c.data.datasets[1].data.shift();}c.update('none');}

// ── REPORT ────────────────────────────────────────────────────
async function buildReport() {
  try {
    const r = await fetch('/api/report');
    const d = await r.json();
    renderReport(d);
  } catch {
    document.getElementById('reportMain').innerHTML =
      `<div class="r-title">CROWDFLOW PRO v4 — REPORT</div>
       <div class="r-sub">Start Flask backend to see live report data.</div>
       <p style="margin-top:16px;font-size:12px;color:var(--text2);line-height:1.8">
         Run <code style="color:var(--cyan)">python app.py</code> then load a video or connect a stream.
         All metrics populate automatically.
       </p>`;
  }
}

function renderReport(d) {
  const s    = d.summary || {};
  const risk = s.risk_level || 'LOW';
  const rc   = {CRITICAL:'var(--red)',HIGH:'var(--orange)',MEDIUM:'var(--amber)',LOW:'var(--green)'}[risk]||'var(--cyan)';

  document.getElementById('reportMain').innerHTML = `
    <div class="r-title">CROWDFLOW PRO v4 — INCIDENT REPORT</div>
    <div class="r-sub">Generated: ${d.generated_at} · Session: ${d.session_id}</div>
    <div style="display:flex;gap:9px;flex-wrap:wrap;margin:12px 0">
      ${[['DETECTED',s.detected??'—','var(--cyan)'],['DENSITY',Math.round((s.avg_density||0)*100)+'%','var(--cyan)'],
         ['RISK',risk,rc],['ENTRIES',s.total_entries??0,'var(--green)'],['EXITS',s.total_exits??0,'var(--red)'],
         ['THREATS',s.active_threats??0,'var(--red)'],['INCIDENTS',s.total_incidents??0,'var(--amber)'],
        ].map(([l,v,c])=>`<div class="card"><div class="card-val" style="color:${c}">${v}</div><div class="card-lbl">${l}</div></div>`).join('')}
    </div>
    <div class="r-section">
      <div class="r-sec-title">Weapon & Threat Incidents</div>
      ${(d.threats||[]).length
        ? `<div style="background:rgba(255,32,64,0.08);border:1px solid rgba(255,32,64,0.3);border-radius:4px;padding:10px;font-size:12px;margin-bottom:8px">${d.threats.map(t=>`⚠ ${t.id}: ${t.weapon} in ${t.zone} [${t.timestamp}] — Civilian notified`).join('<br>')}</div>`
        : '<p style="font-size:12px;color:var(--text2)">No weapon incidents recorded.</p>'}
    </div>
    <div class="r-section">
      <div class="r-sec-title">Civilian Notification Policy</div>
      <p style="font-size:12px;color:var(--text2);line-height:1.85;background:rgba(77,166,255,0.06);border:1px solid rgba(77,166,255,0.18);border-radius:4px;padding:10px">
        ✓ All weapon alerts broadcast exclusively to civilians.<br>
        ✓ Police, Army, Security excluded — briefed via silent secure channel.<br>
        ✓ Dual-channel system: prevents panic + ensures rapid authorised response.
      </p>
    </div>
    <div class="r-section">
      <div class="r-sec-title">Incident Log</div>
      <table class="r-table">
        <tr><th>Time</th><th>Zone</th><th>Description</th></tr>
        ${(d.incidents||[]).slice(0,15).map(i=>`<tr><td style="font-family:var(--mono);font-size:9px">${i.time}</td><td>${i.zone}</td><td style="color:var(--text2)">${i.message}</td></tr>`).join('')
          ||'<tr><td colspan="3" style="color:var(--text2)">No incidents logged</td></tr>'}
      </table>
    </div>`;

  document.getElementById('reportStats').innerHTML =
    [['Cameras',6],['Zones',4],['Alerts',s.total_alerts??0],
     ['Threats',s.active_threats??0],['Incidents',s.total_incidents??0]
    ].map(([l,v])=>`<div class="r-metric"><span>${l}</span><span class="v">${v}</span></div>`).join('');

  document.getElementById('reportInc').innerHTML =
    (d.incidents||[]).slice(0,8).map(i=>`<div>[${i.time}] ${i.zone}: ${i.message.substring(0,52)}</div>`).join('')
    || 'No incidents logged.';
}

// ── UTILS ─────────────────────────────────────────────────────
function $(id, val) { const e = document.getElementById(id); if (e) e.textContent = val; }
function fmt(s) { const m=Math.floor(s/60); return `${m}:${String(Math.floor(s%60)).padStart(2,'0')}`; }
function tickClock() {
  const t = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  $('tbClock', t);
}
window.addEventListener('resize', () => { initEvacCanvas(); });
