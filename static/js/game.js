(function () {

  const API = {
    sessionStart: () => fetch('/api/session/start', { method: 'POST' }).then(r => r.json()),
    levelStart: (index) =>
      fetch('/api/level/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index })
      }).then(r => r.json()),
    levelComplete: (payload) =>
      fetch('/api/level/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(async r => {
        let j = {};
        try { j = await r.json(); } catch {}
        console.log('[complete] status', r.status, 'json', j);
        return { ok: r.ok, status: r.status, json: j };
      })
  };

  class Timer {
    constructor(el) { this.el = el; this.startTs = null; this.tid = null; this.ms = 0; }
    start() { this.startTs = performance.now(); this.ms = 0; this.tid = setInterval(() => this.render(), 100); }
    stop() { if (this.tid) { clearInterval(this.tid); this.tid = null; } }
    render() {
      const now = performance.now();
      const ms = this.startTs ? (now - this.startTs) : 0;
      this.ms = ms;
      const s = Math.floor(ms / 1000), m = Math.floor(s / 60), rem = s % 60;
      this.el.textContent = `${m}:${rem.toString().padStart(2, '0')}`;
    }
    seconds() { return Math.floor(this.ms / 1000); }
  }

  class Puzzle {
    constructor(canvas, hud) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.size = 4; this.grid = []; this.blank = { r: 3, c: 3 };
      this.moves = 0; this.solved = false; this.hud = hud;

      const cssW = parseInt(canvas.getAttribute('width') || canvas.clientWidth || 400, 10);
      const cssH = parseInt(canvas.getAttribute('height') || canvas.clientHeight || 400, 10);
      this.logicalW = cssW; this.logicalH = cssH;

      const ratio = window.devicePixelRatio || 1;
      canvas.width = cssW * ratio; canvas.height = cssH * ratio;
      canvas.style.width = cssW + 'px'; canvas.style.height = cssH + 'px';
      this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

      this.tileSize = this.logicalW / this.size;
      canvas.addEventListener('click', (e) => this.onClick(e));
      this.reset();
    }

    reset() {
      this.grid = []; let n = 1;
      for (let r = 0; r < this.size; r++) { const row = []; for (let c = 0; c < this.size; c++) row.push(n++); this.grid.push(row); }
      this.grid[3][3] = 0; this.blank = { r: 3, c: 3 }; this.moves = 0; this.solved = false;
      this.draw(); this.updateHud();
    }

    updateHud() { if (this.hud) this.hud.textContent = String(this.moves); }
    neighbors(r, c) { return [{ r: r - 1, c }, { r: r + 1, c }, { r, c: c - 1 }, { r, c: c + 1 }].filter(p => p.r >= 0 && p.r < 4 && p.c >= 0 && p.c < 4); }

    shuffle(steps = 50) {
      let last = null;
      for (let i = 0; i < steps; i++) {
        const br = this.blank.r, bc = this.blank.c;
        const nbs = this.neighbors(br, bc);
        const options = nbs.filter(nb => !last || !(nb.r === last.r && nb.c === last.c));
        const choice = options[Math.floor(Math.random() * options.length)];
        this.swap(choice.r, choice.c);
        last = { r: br, c: bc };
      }
      this.moves = 0; this.updateHud(); this.draw();
    }

    swap(r, c) { const br = this.blank.r, bc = this.blank.c; const t = this.grid[r][c]; this.grid[r][c] = 0; this.grid[br][bc] = t; this.blank = { r, c }; }
    canMove(r, c) { const br = this.blank.r, bc = this.blank.c; return (r === br && Math.abs(c - bc) === 1) || (c === bc && Math.abs(r - br) === 1); }

    onClick(e) {
      if (this.solved) return;
      const rect = this.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left, y = e.clientY - rect.top;
      const c = Math.floor(x / this.tileSize), r = Math.floor(y / this.tileSize);
      if (this.grid[r][c] === 0) return;
      if (this.canMove(r, c)) {
        this.swap(r, c); this.moves++; this.updateHud(); this.draw();
        if (this.isSolved()) { this.solved = true; document.dispatchEvent(new CustomEvent('puzzle:solved', { detail: { moves: this.moves } })); }
      }
    }

    isSolved() {
      let n = 1;
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) { if (r === 3 && c === 3) { if (this.grid[r][c] !== 0) return false; } else { if (this.grid[r][c] !== n++) return false; } }
      return true;
    }

    draw() {
      const ctx = this.ctx;
      ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, this.logicalW, this.logicalH);
      ctx.font = 'bold 36px system-ui, Arial, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) {
        const v = this.grid[r][c], x = c * this.tileSize, y = r * this.tileSize;
        ctx.strokeStyle = '#111827'; ctx.lineWidth = 3; ctx.strokeRect(x, y, this.tileSize, this.tileSize);
        if (v !== 0) { ctx.fillStyle = '#e5e7eb'; ctx.fillRect(x + 1, y + 1, this.tileSize - 2, this.tileSize - 2); ctx.fillStyle = '#111827'; ctx.fillText(String(v), x + this.tileSize / 2, y + this.tileSize / 2); }
      }
    }
    manhattanSum() {
      let sum = 0;
      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          const v = this.grid[r][c];
          if (v === 0) continue;
          const goalR = Math.floor((v - 1) / 4);
          const goalC = (v - 1) % 4;
          sum += Math.abs(r - goalR) + Math.abs(c - goalC);
        }
      }
      return sum;
    }

    _cloneGrid() { return this.grid.map(row => row.slice()); }
    _setState(grid, blank) { this.grid = grid.map(row => row.slice()); this.blank = { r: blank.r, c: blank.c }; }

    shuffleToRange(minMD, maxMD, baseSteps = 50, maxTries = 140) {
      let bestGrid = null, bestBlank = null, bestMd = null, bestDiff = Infinity;
      for (let t = 0; t < maxTries; t++) {
        this.reset();
        const steps = baseSteps + Math.floor(Math.random() * 10);
        this.shuffle(steps);
        const md = this.manhattanSum();

        if (md >= minMD && md <= maxMD) {
          this.draw(); this.updateHud();
          return md;
        }
        const diff = md < minMD ? (minMD - md) : (md > maxMD ? md - maxMD : 0);
        if (diff < bestDiff) {
          bestDiff = diff; bestMd = md;
          bestGrid = this._cloneGrid(); bestBlank = { ...this.blank };
        }
      }
      if (bestGrid) {
        this._setState(bestGrid, bestBlank);
        this.draw(); this.updateHud();
        return bestMd;
      }
      this.reset(); this.shuffle(baseSteps);
      this.draw(); this.updateHud();
      return this.manhattanSum();
    }

  }

  async function initStudy() {
    const planRes = await API.sessionStart();
    console.log('[sessionStart]', planRes);
    if (!planRes.ok) { alert('Failed to start session'); return; }
    const plan = planRes.plan.sort((a, b) => a.index - b.index);
    console.log('[plan]', plan);

    const tlxOrdersByIndex = {};
    plan.forEach(p => {
      tlxOrdersByIndex[p.index] = Array.isArray(p.tlx_order) ? p.tlx_order.slice() : [];
    });
    let pendingTlx = [];
    let currentIndex = plan.find(p => !p.completed)?.index ?? 1;

    const canvas = document.getElementById('puzzle');
    const timerEl = document.getElementById('timer');
    const movesEl = document.getElementById('moves');
    const levelEl = document.getElementById('levelLabel');
    const difficultyEl = document.getElementById('difficultyLabel');
    const startBtn = document.getElementById('startBtn');
    const submitBtn = document.getElementById('submitBtn');
    const quitBtn = document.getElementById('quitBtn');
    const messageEl = document.getElementById('message');

    const pz = new Puzzle(canvas, movesEl);
    const timer = new Timer(timerEl);

    let currentMinTime = 0; let quitWatch = null;
    const stopQuitWatch = () => { if (quitWatch) { clearInterval(quitWatch); quitWatch = null; } };

    function tlxBusy(on) {
      const el = document.getElementById('tlxBusy');
      if (!el) return;
      if (on) { el.classList.remove('hidden'); el.classList.add('flex'); }
      else    { el.classList.add('hidden');     el.classList.remove('flex'); }
    }

    function resetTlxInputs() {
      (window.TLX_DIMS || []).forEach(dim => {
        const safe = dim.replace(/\s+/g, '_');
        const s = document.getElementById('tlx_' + safe); if (s) s.value = 4;
        const t = document.getElementById('tlx_text_' + safe);
        if (t) { t.value = ''; t.classList.remove('border-red-500'); }
      });
      const msgS = document.getElementById('tlxMsg');     if (msgS) msgS.textContent = '';
      const msgD = document.getElementById('tlxMsgDesc'); if (msgD) msgD.textContent = '';
      tlxBusy(false);
    }

    function openTLXModal(type, idx) {
      console.log('[TLX] opening modal', { index: idx, type });

      const modal = document.getElementById('tlxModal');
      const title = document.getElementById('tlxTitle');
      const formS = document.getElementById('tlxSliderForm');
      const formD = document.getElementById('tlxDescForm');
      if (!modal) { nextLevel(); return; }

      resetTlxInputs();

      if (type === 'slider') {
        title.textContent = `NASA-TLX (Sliders) — Level ${idx}`;
        formS.classList.remove('hidden'); formD.classList.add('hidden');
      } else {
        title.textContent = `NASA-TLX (Descriptive) — Level ${idx}`;
        formD.classList.remove('hidden'); formS.classList.add('hidden');
      }
      modal.classList.remove('hidden'); modal.classList.add('flex');

      if (!window._tlxBound) {
        document.getElementById('tlxSubmitSlider')?.addEventListener('click', async () => {
          const ratings = {};
          (window.TLX_DIMS || []).forEach(dim => {
            const id = 'tlx_' + dim.replace(/\s+/g,'_');
            ratings[dim] = parseInt(document.getElementById(id).value, 10);
          });
          console.log('[TLX] submit slider', { index: currentIndex, ratings });
          const r = await fetch('/api/tlx/submit', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ index: currentIndex, type:'slider', ratings })
          });
          const j = await r.json().catch(()=>({}));
          console.log('[TLX] slider response', r.status, j);
          if (r.ok && j.ok) {
            if (pendingTlx.length > 0) openTLXModal(pendingTlx.shift(), currentIndex);
            else { closeTLXModal(); nextLevel(); }
          } else {
            document.getElementById('tlxMsg').textContent = (j.failed && j.failed[0]?.reason) || 'Please complete all sliders (1–7).';
          }
        });

        document.getElementById('tlxSubmitDesc')?.addEventListener('click', async () => {
          const btn = document.getElementById('tlxSubmitDesc');
          const notes = {};
          (window.TLX_DIMS || []).forEach(dim => {
            const id = 'tlx_text_' + dim.replace(/\s+/g,'_');
            notes[dim] = (document.getElementById(id).value || "").trim();
          });

          console.log('[TLX] submit descriptive', { index: currentIndex, notes });
          tlxBusy(true); btn.disabled = true;
          document.getElementById('tlxMsgDesc').textContent = 'Validating responses…';

          const r = await fetch('/api/tlx/submit', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ index: currentIndex, type:'descriptive', notes })
          });
          const j = await r.json().catch(()=>({}));
          console.log('[TLX] descriptive response', r.status, j);

          (window.TLX_DIMS || []).forEach(dim => {
            const id = 'tlx_text_' + dim.replace(/\s+/g,'_');
            document.getElementById(id)?.classList.remove('border-red-500');
          });

          tlxBusy(false); btn.disabled = false;

          if (r.ok && j.ok) {
            document.getElementById('tlxMsgDesc').textContent = '';
            if (pendingTlx.length > 0) openTLXModal(pendingTlx.shift(), currentIndex);
            else { closeTLXModal(); nextLevel(); }
          } else {
            const fails = j.failed || [];
            let msg = `Please revise:\n`;
            fails.forEach(f => {
              const id = 'tlx_text_' + f.dimension.replace(/\s+/g,'_');
              document.getElementById(id)?.classList.add('border-red-500');
              msg += `• ${f.dimension}: ${f.reason}\n`;
            });
            document.getElementById('tlxMsgDesc').textContent = msg.trim();
          }
        });

        window._tlxBound = true;
      }
    }

    function closeTLXModal(){
      const modal = document.getElementById('tlxModal');
      if (!modal) return;
      modal.classList.add('hidden'); modal.classList.remove('flex');
    }

    function loadLevel(idx) {
      const info = plan.find(p => p.index === idx);
      levelEl.textContent = `Level ${info.index} of ${plan.length}`;
      if (difficultyEl) { difficultyEl.textContent = ''; difficultyEl.style.display = 'none'; }
      pz.reset(); messageEl.textContent = '';
      submitBtn.disabled = true; quitBtn.disabled = true; startBtn.disabled = false;
      stopQuitWatch(); currentMinTime = 0;
    }

    startBtn.addEventListener('click', async () => {
      startBtn.disabled = true;
      const r = await API.levelStart(currentIndex);
      console.log('[levelStart]', r);
      if (!r.ok) { alert('Could not start level'); startBtn.disabled = false; return; }
      if (typeof r.md_min === 'number' && typeof r.md_max === 'number') {
        const got = pz.shuffleToRange(r.md_min, r.md_max, r.shuffle_steps || 50, 140);
        console.log('[difficulty] target MD', r.md_min, r.md_max, '→ got', got);
      } else {
        pz.reset(); pz.shuffle(r.shuffle_steps);
      }
      submitBtn.disabled = false;
      currentMinTime = r.min_time || 0;
      timer.start();
      quitBtn.disabled = true;
      stopQuitWatch();
      quitWatch = setInterval(() => {
        const secs = timer.seconds();
        if (secs >= currentMinTime) { quitBtn.disabled = false; stopQuitWatch(); messageEl.textContent = 'Minimum time reached — you may quit this level.'; }
      }, 300);
    });

    document.addEventListener('puzzle:solved', () => {
      timer.stop();
      messageEl.textContent = `Solved! Moves: ${pz.moves} — Time: ${timer.el.textContent}.`;
      submitBtn.disabled = false;
    });

    async function completeLevel(asCompleted) {
      submitBtn.disabled = true; quitBtn.disabled = true;
      const resp = await API.levelComplete({ index: currentIndex, moves: pz.moves, time_ms: Math.round(timer.ms), completed: !!asCompleted });
      const payload = resp.json || {}; const code = payload.error || payload.detail || '';
      const remaining = typeof payload.min_remaining === 'number' ? payload.min_remaining : null;

      if ((!resp.ok && (code === 'min_time_not_reached' || remaining !== null)) || (resp.ok && remaining !== null)) {
        let remain = remaining ?? Math.max(0, (currentMinTime - timer.seconds()));
        const tick = setInterval(async () => {
          remain -= 1; messageEl.textContent = `Please keep this page open — ${remain}s remaining...`;
          if (remain <= 0) {
            clearInterval(tick);
            const retry = await API.levelComplete({ index: currentIndex, moves: pz.moves, time_ms: Math.round(timer.ms), completed: !!asCompleted });
            if (retry.ok) {
              messageEl.textContent = 'Recorded. Please complete a short questionnaire.';
              pendingTlx = (tlxOrdersByIndex[currentIndex] || []).slice();
              if (pendingTlx.length > 0) openTLXModal(pendingTlx.shift(), currentIndex);
              else nextLevel();
            } else {
              const j = retry.json || {};
              messageEl.textContent = j.detail || 'Still too early, please try again.';
              submitBtn.disabled = !pz.solved;
              if (timer.seconds() >= currentMinTime) quitBtn.disabled = false;
            }
          }
        }, 1000);
        return;
      }

      if (resp.ok) {
        messageEl.textContent = 'Recorded. Please complete a short questionnaire.';
        pendingTlx = (tlxOrdersByIndex[currentIndex] || []).slice();
        if (pendingTlx.length > 0) openTLXModal(pendingTlx.shift(), currentIndex);
        else nextLevel();
      } else {
        messageEl.textContent = typeof code === 'string' && code ? code : 'Error recording result. Try again.';
        submitBtn.disabled = !pz.solved;
        if (timer.seconds() >= currentMinTime) quitBtn.disabled = false;
      }
    }

    submitBtn.addEventListener('click', async () => {
      if (!pz.solved) {
        messageEl.textContent = 'Puzzle is not solved. Please try again.';
        messageEl.classList.remove('text-green-700');
        messageEl.classList.add('text-red-700');
        setTimeout(() => { messageEl.classList.remove('text-red-700'); }, 1500);
        return;
      }
      await completeLevel(true);
    });

    quitBtn.addEventListener('click', async () => { timer.stop(); await completeLevel(false); });

    function nextLevel() {
      stopQuitWatch();
      if (currentIndex < plan.length) {
        currentIndex += 1;
        console.log('[TLX] next level loaded', { currentIndex, tlx_order: tlxOrdersByIndex[currentIndex] });
        loadLevel(currentIndex);
        timerEl.textContent = '0:00'; movesEl.textContent = '0';
      } else {
        window.location.href = '/post';
      }
    }

    loadLevel(currentIndex);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initStudy);
  else initStudy();

})();
