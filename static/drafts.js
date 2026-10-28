/* Tab-local composer drafts only. Credential/proxy/settings fields are never read. */
const ComposerDraft = (() => {
  const key = 'dot:composer:v1', ttl = 8*60*60*1000;
  const sensitive = text => /sk-[a-z0-9_-]{16,}|[a-f0-9]{32}\.[a-z0-9]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_ -]?key|password|كلمة\s*المرور)\s*[:=]\s*\S+|https?:\/\/[^\s/]+:[^\s/]+@|\b(?:\d{1,3}\.){3}\d{1,3}:\d+:[^\s:]+:[^\s]+/i.test(text);
  function clear() { try { sessionStorage.removeItem(key); } catch {} }
  function save(value) {
    if (!value.text?.trim() || sensitive(value.text)) { clear(); return; }
    try { sessionStorage.setItem(key,JSON.stringify({...value,text:value.text.slice(0,12000),savedAt:Date.now()})); } catch {}
  }
  function load() {
    try {
      const value = JSON.parse(sessionStorage.getItem(key) || 'null');
      if (!value || typeof value.text !== 'string' || value.text.length>12000 || sensitive(value.text) || !Number.isFinite(value.savedAt) || Date.now()-value.savedAt>ttl || value.savedAt>Date.now()+60000 || (value.taskId!==null && typeof value.taskId!=='string') || (value.editId!==null && typeof value.editId!=='string') || typeof value.newTask!=='boolean') { clear(); return null; }
      return value;
    } catch { clear(); return null; }
  }
  return { save, load, clear };
})();
