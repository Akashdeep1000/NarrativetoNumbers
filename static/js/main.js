(function () {
  function parseNiceMessage(text) {
    try {
      const j = JSON.parse(text);
      if (typeof j.detail === 'string') return j.detail;
      if (Array.isArray(j.detail)) return j.detail.map(e => e.msg || (e.loc ? e.loc.join('.') : '')).join('\n');
      if (j.error) return j.error;
      if (j.message) return j.message;
      return JSON.stringify(j);
    } catch {
      return text || 'Something went wrong.';
    }
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const text = await res.text();
    let json = null;
    try { json = JSON.parse(text); } catch {}
    return { ok: res.ok, status: res.status, text, json };
  }

  document.addEventListener('DOMContentLoaded', () => {
    
    const form = document.getElementById('demo-form');
    if (form && !form.dataset.bound) {
      form.dataset.bound = '1';
      const msgEl = document.getElementById('demogMsg'); 

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!form.reportValidity()) return;

        const age = parseInt(form.querySelector('#age')?.value || '0', 10);
        let gender = form.querySelector('input[name="gender"]:checked')?.value || '';
        const other = (form.querySelector('#gender_other')?.value || '').trim();
        if (gender === 'self_describe') {
          gender = other || 'Prefer to self-describe';
        }
        const experience = form.querySelector('#experience')?.value || '';

        const payload = { age, gender, experience };
        if (msgEl) msgEl.textContent = 'Saving…';

        const result = await postJson('/api/demographics', payload);
        if (result.ok) {
          if (msgEl) msgEl.textContent = '';
          window.location.href = '/study';
        } else {
          const nice = parseNiceMessage(result.text);
          if (msgEl) msgEl.textContent = nice;
          console.error('[demographics] submit failed', result.status, result.text);
          
        }
      });
    }

    
    window.addEventListener('unhandledrejection', (ev) => {
      console.error('[unhandledrejection]', ev.reason);
    });
  });
})();
