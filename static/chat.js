/* DOM-only rendering after Marked + DOMPurify. No remote images, styles or HTML controls. */
const ChatContent = (() => {
  const rendered = new WeakMap();
  const tags = ['p','br','strong','em','del','code','pre','blockquote','ul','ol','li','h1','h2','h3','h4','a','table','thead','tbody','tr','th','td','hr'];
  function render(element, text, rich) {
    const signature = (rich ? 'rich:' : 'text:') + text;
    if (rendered.get(element) === signature) return;
    rendered.set(element, signature);
    element.classList.toggle('rich-text', rich);
    if (!rich) { element.textContent = text; return; }
    try {
      const html = marked.parse(text, { async: false, breaks: true, gfm: true });
      const fragment = DOMPurify.sanitize(html, { RETURN_DOM_FRAGMENT: true, ALLOWED_TAGS: tags, ALLOWED_ATTR: ['href','title'], ALLOW_DATA_ATTR: false, ALLOW_ARIA_ATTR: false });
      for (const a of fragment.querySelectorAll('a')) {
        let safe = false;
        try { const url = new URL(a.getAttribute('href')); safe = ['https:','http:'].includes(url.protocol) && !url.username && !url.password; } catch {}
        if (safe) { a.target = '_blank'; a.rel = 'noopener noreferrer'; a.referrerPolicy = 'no-referrer'; }
        else a.replaceWith(...a.childNodes);
      }
      for (const pre of fragment.querySelectorAll('pre')) {
        const code = pre.querySelector('code');
        if (!code) continue;
        const wrapper = document.createElement('div'); wrapper.className = 'code-block';
        const header = document.createElement('div'); header.className = 'code-heading';
        const label = document.createElement('span'); label.textContent = 'كود';
        const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'icon-button'; copy.setAttribute('aria-label','نسخ الكود'); copy.title = 'نسخ الكود';
        const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
        const use = document.createElementNS(svg.namespaceURI,'use'); use.setAttribute('href','#i-copy'); svg.append(use); copy.append(svg);
        copy.onclick = async () => {
          const text = code.textContent;
          try {
            if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
            else {
              const selection = getSelection(), ranges = [];
              for (let i=0; i<selection.rangeCount; i++) ranges.push(selection.getRangeAt(i).cloneRange());
              const range = document.createRange(); range.selectNodeContents(code); selection.removeAllRanges(); selection.addRange(range);
              const ok = document.execCommand('copy'); selection.removeAllRanges(); for (const previous of ranges) selection.addRange(previous);
              if (!ok) throw Error('Clipboard unavailable');
            }
            toast('تم نسخ الكود');
          } catch { toast('تعذر النسخ؛ حدد الكود وانسخه يدويًا'); }
        };
        header.append(label,copy); pre.replaceWith(wrapper); wrapper.append(header,pre);
      }
      for (const table of fragment.querySelectorAll('table')) {
        const wrap = document.createElement('div'); wrap.className = 'table-scroll'; table.replaceWith(wrap); wrap.append(table);
      }
      element.replaceChildren(fragment);
    } catch { element.classList.remove('rich-text'); element.textContent = text; }
  }
  return { render };
})();

const ChatView = (() => {
  const scroll = document.getElementById('chatScroll'), rows = document.getElementById('messages'), jump = document.getElementById('jumpLatest');
  let taskId, keys = new Set(), unseen = 0, following = true, frame, maxEventSeq = 0, maxMessageTime = 0, maxMessageCursor = 0;
  const nearBottom = () => scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 64;
  function badge() { jump.hidden = following || unseen === 0; jump.querySelector('.new-count').textContent = Math.min(99,unseen); jump.setAttribute('aria-label','عرض آخر '+unseen+' رسالة أو حدث'); }
  function latest() { following = true; unseen = 0; cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { scroll.scrollTop = scroll.scrollHeight; badge(); }); }
  scroll.addEventListener('scroll', () => { following = nearBottom(); if (following) unseen = 0; badge(); }, { passive: true });
  jump.onclick = latest;
  new ResizeObserver(() => { if (following) latest(); }).observe(scroll);
  function before(id) {
    if (taskId !== id) { taskId = id; keys = new Set(); unseen = 0; following = true; maxEventSeq = 0; maxMessageTime = 0; maxMessageCursor = 0; }
    const top = scroll.getBoundingClientRect().top;
    const anchor = [...rows.children].find(el => el.getBoundingClientRect().bottom > top);
    return anchor ? { key: anchor.dataset.rowKey, offset: anchor.getBoundingClientRect().top - top } : null;
  }
  function after(anchor) {
    const elements = [...rows.children], next = new Set(elements.map(el => el.dataset.rowKey));
    // Equal timestamps are common: identify archive rows by their stable cursor,
    // or, when unavailable, their position relative to an already seen message.
    const equalTimeFrontier = elements.reduce((last,el,index) => !el.dataset.eventSeq && keys.has(el.dataset.rowKey) && Number(el.dataset.rowTime)===maxMessageTime ? index : last, -1);
    if (!following) unseen += elements.filter((el,index) => {
      if (keys.has(el.dataset.rowKey)) return false;
      if (el.dataset.eventSeq) return Number(el.dataset.eventSeq) > maxEventSeq;
      const cursor=Number(el.dataset.messageCursor)||0, time=Number(el.dataset.rowTime)||0;
      if (cursor && maxMessageCursor) return cursor > maxMessageCursor;
      return time > maxMessageTime || (time === maxMessageTime && equalTimeFrontier >= 0 && index > equalTimeFrontier);
    }).length;
    for (const el of elements) {
      if (el.dataset.eventSeq) maxEventSeq = Math.max(maxEventSeq,Number(el.dataset.eventSeq));
      else { maxMessageTime = Math.max(maxMessageTime,Number(el.dataset.rowTime)||0); maxMessageCursor = Math.max(maxMessageCursor,Number(el.dataset.messageCursor)||0); }
    }
    keys = next;
    if (following) latest();
    else {
      const item = [...rows.children].find(el => el.dataset.rowKey === anchor?.key);
      if (item) scroll.scrollTop += item.getBoundingClientRect().top - scroll.getBoundingClientRect().top - anchor.offset;
      badge();
    }
  }
  return { before, after, latest };
})();
