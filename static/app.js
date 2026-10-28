const $=id=>document.getElementById(id);
let csrf='',authenticated=false,busy=false,live=null,stream=null,lastState=null,editing=null,newTaskMode=false,zoom=1,viewport={width:1280,height:800},messageSignature='',eventSignature='',filesSignature='',blankPage=false,toastTimer,reconnectTimer,addressURL='',addressDirty=false,phaseKey='',phaseTime=0,phaseIdleTimer,layoutTimer,layoutPending=false,layoutQueued=true,layoutPromise=null,submitting=false;
let streamCursor='';
let sessionCheckPending=false,sessionCheckTime=0;
let manualVerification=false,draftRestored=false,beforeEdit=null,stateConnected=false,viewConnected=false,frameWaiting=false;
let announcementTask=null,announcementSeq=0,announcementMessages=new Set();
const imageURLs=new Set();
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
const labels={starting:'يجهّز المهمة',running:'يعمل الآن',paused:'التحكم ليك',waiting_approval:'موافقة مطلوبة',waiting_user:'بانتظارك',completed:'تم',failed:'توقفت المهمة',cancelled:'متوقف'};
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');const use=document.createElementNS(svg.namespaceURI,'use');use.setAttribute('href','#i-'+name);svg.append(use);return svg}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4000)}
async function api(path,body,method){const response=await fetch('/api/'+path,{method:method||(body===undefined?'GET':'POST'),headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},...(body!==undefined?{body:JSON.stringify(body)}:{})});let data;try{data=await response.json()}catch{data={detail:'تعذر الاتصال'}}if(!response.ok){if(response.status===401)showLogin();throw Error(typeof data.detail==='string'?data.detail:'راجع البيانات')}return data}
function disconnect(){cancelPendingFrame();streamCursor='';stateConnected=false;viewConnected=false;clearTimeout(reconnectTimer);if(live){live.onclose=null;live.close();live=null}if(stream){stream.close();stream=null}for(const url of imageURLs)URL.revokeObjectURL(url);imageURLs.clear()}
function showLogin(){authenticated=false;disconnect();if(!$('loginDialog').open)$('loginDialog').showModal()}
async function connect(){const s=await api('session');csrf=s.csrf;authenticated=true;$('model').textContent=s.provider+' / '+s.model;if(!s.configured)toast('أضف مفتاح الموديل من الإعدادات');if($('loginDialog').open)$('loginDialog').close();events();render(await api('state'))}
function updateConnection(){const waiting=!!lastState?.browser_ready&&(!viewConnected||frameWaiting);const offline=!stateConnected||waiting;$('connection').textContent=offline?'يعيد الاتصال':'متصل';$('connectionDot').classList.toggle('offline',offline);$('connectionNotice').hidden=!offline||!authenticated||document.hidden;$('connectionNotice').textContent=!stateConnected?(!$('screen').hidden&&$('screen').getAttribute('src')?'يعيد الاتصال؛ آخر عرض محفوظ':'يعيد الاتصال'):'يعيد توصيل العرض';$('reconnecting').hidden=!waiting||document.hidden}
async function checkSessionAfterDisconnect(source){
 if(!authenticated||sessionCheckPending||Date.now()-sessionCheckTime<3000)return;
 sessionCheckPending=true;sessionCheckTime=Date.now();
 try{const response=await fetch('/api/session',{cache:'no-store'});if(authenticated&&stream===source&&response.status===401)showLogin()}catch{}finally{sessionCheckPending=false}
}
function events(){if(stream)stream.close();stateConnected=false;const source=new EventSource('/api/events'+(streamCursor?'?cursor='+encodeURIComponent(streamCursor):''));stream=source;source.onopen=()=>{if(stream!==source)return;stateConnected=true;updateConnection()};source.onmessage=e=>{if(stream!==source)return;try{if(e.lastEventId)streamCursor=e.lastEventId;stateConnected=true;render(JSON.parse(e.data))}catch(error){console.error('State update failed',error)}};source.onerror=()=>{if(stream!==source)return;stateConnected=false;updateConnection();checkSessionAfterDisconnect(source)}}
function compactURL(url){try{return new URL(url).hostname.replace(/^www\./,'')}catch{return url}}
function setAddress(url){if(url==='about:blank')return;addressURL=url;if(document.activeElement!==$('url')&&!addressDirty)$('url').value=compactURL(url);$('url').title=url}
function normalizeURL(value){value=value.trim();return value&&!/^[a-z][a-z\d+.-]*:/i.test(value)?'https://'+value:value}
function currentAddress(){return normalizeURL(addressDirty?$('url').value:addressURL||$('url').value)}
$('url').addEventListener('focus',()=>{if(!addressDirty&&addressURL)$('url').value=addressURL});$('url').addEventListener('input',()=>addressDirty=true);$('url').addEventListener('blur',()=>{if(!addressDirty)$('url').value=compactURL(addressURL)});
function fitFrame(){const view=$('viewport'),stage=$('browserStage');if(!view.clientWidth)return;const ratio=viewport.width/viewport.height;const focused=$('browserCard').classList.contains('focus-mode');const base=focused?Math.min(view.clientWidth,view.clientHeight*ratio):view.clientWidth;const width=Math.round(base*zoom*100)/100;if(Math.abs(stage.getBoundingClientRect().width-width)>.1)stage.style.width=width+'px';stage.style.aspectRatio=viewport.width+' / '+viewport.height;$('browserCard').style.setProperty('--frame-height',Math.round(base/ratio)+'px')}
$('screen').onload=()=>{const screen=$('screen');if(screen.naturalWidth&&screen.naturalHeight)viewport={width:screen.naturalWidth,height:screen.naturalHeight};fitFrame()};
// Decode one frame at a time; retain only the newest waiting blob. Cancelling
// every in-flight decode can starve the viewer when frames arrive faster.
let pendingFrame=null, queuedFrame=null;
function cancelPendingFrame(){queuedFrame=null;if(!pendingFrame)return;pendingFrame.image.onload=pendingFrame.image.onerror=null;URL.revokeObjectURL(pendingFrame.url);imageURLs.delete(pendingFrame.url);pendingFrame=null}
function setBrowserFrame(blob){
 if(pendingFrame){queuedFrame=blob;return}
 const url=URL.createObjectURL(blob), image=new Image(), pending={url,image};
 imageURLs.add(url);pendingFrame=pending;
 const next=()=>{if(queuedFrame){const blob=queuedFrame;queuedFrame=null;setBrowserFrame(blob)}};
 image.onload=()=>{
  if(pendingFrame!==pending)return;
  pendingFrame=null;const screen=$('screen');screen.src=url;
  for(const previous of imageURLs)if(previous!==url){URL.revokeObjectURL(previous);imageURLs.delete(previous)}
  screen.hidden=false;$('empty').hidden=true;frameWaiting=false;updateConnection();next();
 };
 image.onerror=()=>{if(pendingFrame!==pending)return;pendingFrame=null;URL.revokeObjectURL(url);imageURLs.delete(url);next()};
 image.src=url;
}
function browserLive(){
 if(live||!authenticated||document.hidden)return;
 const socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/browser/live');live=socket;socket.binaryType='blob';
 socket.onopen=()=>{if(live!==socket)return;viewConnected=true;updateConnection()};
 socket.onmessage=e=>{if(live!==socket)return;if(typeof e.data==='string'){const data=JSON.parse(e.data);if(data.viewport)viewport=data.viewport;if(data.url){blankPage=data.url==='about:blank';if(!blankPage)setAddress(data.url)}if(data.status==='closed'||blankPage){cancelPendingFrame();$('screen').hidden=true;$('empty').hidden=false;frameWaiting=false}else if(data.status==='waiting')frameWaiting=true;updateConnection();return}if(blankPage){$('screen').hidden=true;$('empty').hidden=false;frameWaiting=false;updateConnection();return}setBrowserFrame(e.data)};
 socket.onclose=()=>{if(live!==socket)return;live=null;viewConnected=false;updateConnection();if(authenticated&&!document.hidden)reconnectTimer=setTimeout(browserLive,2200)}
}
function timestamp(time){return new Date(time*1000).toLocaleTimeString('ar-EG',{hour:'2-digit',minute:'2-digit'})}
function announceLive(task){
 const id=task?.id||null,events=task?.events||[],messages=task?.messages||[];
 if(id!==announcementTask){announcementTask=id;announcementSeq=Math.max(0,...events.map(e=>e.seq||0));announcementMessages=new Set(messages.map(m=>m.id));$('chatAnnouncement').textContent='';return}
 if(!id)return;
 const freshEvents=events.filter(e=>e.seq>announcementSeq),freshReplies=messages.filter(m=>m.role==='assistant'&&!announcementMessages.has(m.id));
 announcementSeq=Math.max(announcementSeq,...events.map(e=>e.seq||0));announcementMessages=new Set(messages.map(m=>m.id));
 const latest=freshReplies.at(-1)||freshEvents.at(-1);
 if(latest)$('chatAnnouncement').textContent=(latest.content||latest.title||'').slice(0,200);
}
function renderMessages(messages,events=[],task=null){
const sig=JSON.stringify([task?.id,messages,events,busy]);if(sig===messageSignature)return;messageSignature=sig;
const anchor=ChatView.before(task?.id||'empty'),container=$('messages');
const start=task?.created||events[0]?.time||0,end=events.at(-1)?.time||start;
const rows=messages.map((m,i)=>({key:'message:'+m.id,type:'message',data:m,time:m.time??((m.role==='user'?start-1:end+1)+i/1000)}));
for(const e of events){if(e.kind==='step')continue;rows.push({key:'event:'+(task?.id||'')+':'+e.seq,type:'event',data:e,time:e.time||0})}
rows.sort((a,b)=>a.time-b.time);const existing=new Map([...container.children].map(el=>[el.dataset.rowKey,el])),keep=new Set();
const lastEvent=rows.filter(r=>r.type==='event').at(-1)?.key;
rows.forEach((row,index)=>{keep.add(row.key);let item=existing.get(row.key);const m=row.data;if(!item){item=document.createElement('article');item.dataset.rowKey=row.key;
 if(row.type==='event'){item.className='activity-message';const marker=document.createElement('span');marker.className='activity-marker';marker.setAttribute('aria-hidden','true');const text=document.createElement('span');text.className='activity-text';const elapsed=document.createElement('time');elapsed.className='activity-elapsed';elapsed.setAttribute('aria-hidden','true');item.append(marker,text,elapsed)}
 else{item.dataset.messageId=m.id;item.className='chat-message '+m.role;const bubble=document.createElement('div');bubble.className='message-bubble';item.append(bubble);if(m.role==='user'){const footer=document.createElement('div');footer.className='message-footer';const edit=document.createElement('button');edit.type='button';edit.className='edit-message';edit.setAttribute('aria-label','تعديل رسالتك');edit.title='تعديل';edit.append(icon('edit'));footer.append(edit);item.append(footer)}}}
 item.dataset.rowTime=String(row.time||0);
 if(row.type==='message'&&Number.isSafeInteger(m.archive_cursor))item.dataset.messageCursor=String(m.archive_cursor);
 if(row.type==='event'){const active=busy&&row.key===lastEvent;item.classList.toggle('active',active);item.classList.toggle('event-error',m.kind==='error');item.dataset.eventSeq=m.seq;item.dataset.eventTime=m.time||0;item.querySelector('.activity-marker').textContent=['action_done','completed'].includes(m.kind)?'✓':m.kind==='error'?'!':'·';const duplicateError=m.kind==='error'&&messages.some(message=>message.role==='assistant'&&message.content===m.title);const text=m.kind==='completed'?'اكتملت المهمة':duplicateError?'توقفت المهمة — التفاصيل في الرد':m.title;const label=item.querySelector('.activity-text');if(label.textContent!==text)label.textContent=text;if(!active)item.querySelector('time').textContent=''}
 else{item.classList.toggle('outdated',!!m.outdated);item.setAttribute('aria-label',m.role==='user'?'رسالتك':'رد dot');const bubble=item.querySelector('.message-bubble');ChatContent.render(bubble,m.content,m.role==='assistant');const edit=item.querySelector('.edit-message');if(edit){edit.hidden=!!m.read_only;edit.onclick=()=>beginEdit(m)}}
 if(container.children[index]!==item)container.insertBefore(item,container.children[index]||null)});
for(const el of [...container.children])if(!keep.has(el.dataset.rowKey))el.remove();tickActivity();ChatView.after(anchor)}
function tickActivity(){const active=document.querySelector('.activity-message.active');if(!active)return;const seconds=Math.max(0,Math.floor(Date.now()/1000-Number(active.dataset.eventTime)));active.querySelector('time').textContent=seconds<60?seconds+'ث':Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')}
function renderEvents(events){
 const sig=JSON.stringify(events);if(sig===eventSignature)return;
 const panel=$('activityPanel'),list=$('activityList'),stick=panel.scrollHeight-panel.scrollTop-panel.clientHeight<64;
 eventSignature=sig;$('eventCount').textContent=events.length;
 if(!events.length){if(!list.querySelector('.activity-placeholder')){const li=document.createElement('li');li.className='activity-placeholder';li.textContent='لا خطوات بعد';list.replaceChildren(li)}return}
 const existing=new Map([...list.children].filter(el=>el.dataset.eventSeq).map(el=>[el.dataset.eventSeq,el])),keep=new Set();
 events.forEach((event,index)=>{
  const key=String(event.seq);keep.add(key);let li=existing.get(key);
  if(!li){li=document.createElement('li');li.dataset.eventSeq=key;const mark=document.createElement('span');mark.className='event-icon';const label=document.createElement('span');const time=document.createElement('time');li.append(mark,label,time)}
  const mark=li.children[0],label=li.children[1],time=li.children[2];
  const symbol=event.kind==='action_done'||event.kind==='completed'?'✓':event.kind==='error'?'!':'·';
  if(mark.textContent!==symbol)mark.textContent=symbol;if(label.textContent!==event.title)label.textContent=event.title;
  const stamp=timestamp(event.time);if(time.textContent!==stamp)time.textContent=stamp;
  if(list.children[index]!==li)list.insertBefore(li,list.children[index]||null);
 });
 for(const el of [...list.children])if(!keep.has(el.dataset.eventSeq))el.remove();
 if(panel.open&&stick)panel.scrollTop=panel.scrollHeight;
}
function shortPhase(event,task){if(!busy)return labels[task?.status]||'';if(task?.status==='waiting_approval'||task?.status==='waiting_user')return labels[task.status];const title=event?.title||task?.message||'';const replacements={'انتظار رد الموديل لتحديد الفعل التالي':'ينتظر الموديل','وصل رد الموديل؛ تجهيز خطوة المتصفح':'يجهّز الخطوة','قراءة الصفحة لتحديد الخطوة التالية':'يقرأ الصفحة','النقر على عنصر في الصفحة':'ينقر على الصفحة','الكتابة في حقل':'يكتب في الحقل','تجهيز الرد النهائي':'يجهّز الرد','استخراج البيانات من الصفحة':'يجمع البيانات','تمرير الصفحة':'يمرّر الصفحة','بدأت المهمة':'يبدأ المهمة'};return (replacements[title]||title).slice(0,60)}
function tickPhase(){tickActivity();if(busy&&phaseTime){const seconds=Math.max(0,Math.floor(Date.now()/1000-phaseTime));$('eventElapsed').textContent=seconds<60?seconds+'ث':Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')}else $('eventElapsed').textContent=''}
function renderPhase(task){const events=task?.events||[];const event=events[events.length-1];const key=(task?.id||'')+':'+(event?.seq||0)+':'+task?.status;const text=shortPhase(event,task);if(key!==phaseKey||$('message').textContent==='يعيد الاتصال…'){phaseKey=key;phaseTime=event?.time||task?.updated||task?.created||0;clearTimeout(phaseIdleTimer);$('message').textContent=text;$('activityOpen').hidden=!text;if(!reducedMotion.matches&&text)$('message').animate([{opacity:0,transform:'translateY(3px)'},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'cubic-bezier(.2,.8,.2,1)'});if(task&&['completed','cancelled'].includes(task.status))phaseIdleTimer=setTimeout(()=>{$('activityOpen').hidden=true;syncDock()},10000)}$('activityOpen').classList.toggle('running',busy);tickPhase()}
function render(state){lastState=state;busy=state.busy;viewport=state.viewport||viewport;const task=state.task;restoreComposerDraft(task);manualVerification=task?.status==='waiting_user'&&task?.pending?.name==='verification';const verification=task?.verification;const showVerification=state.busy&&verification&&['detected','checking','needs_user','ai_solving'].includes(verification.state);$('verificationBar').hidden=!showVerification;$('verificationLabel').textContent=verification?.detail||'';$('verificationBar').dataset.state=verification?.state||'';updateConnection();$('open').disabled=busy;$('takeover').disabled=!state.browser_ready;$('takeover').setAttribute('aria-pressed',String(state.browser_ready&&!busy));$('keyboardOpen').disabled=!state.browser_ready||(busy&&!manualVerification);$('cancel').hidden=!busy;$('resume').hidden=busy||!task||!['paused','failed'].includes(task.status);$('statusTitle').textContent=task?labels[task.status]||task.status:'';$('steps').textContent=task?.steps||0;$('approval').hidden=!task||manualVerification||!['waiting_approval','waiting_user'].includes(task.status);$('proposal').textContent=task?.pending?.detail||'';$('proxyBadge').textContent=state.proxy?.enabled?'البروكسي مفعّل':'اتصال افتراضي';$('settingsOpen').title=state.proxy?.enabled?'الإعدادات · البروكسي مفعّل':'الإعدادات';const timeline=syncHistory(task,state.replay);renderMessages(syncMessageHistory(task,state.message_history),timeline.slice(-500),task);renderEvents(timeline);queueReplay(task,state.replay);announceLive(task);renderUsage(state.usage);renderPhase(task);const fs=JSON.stringify(state.files);if(fs!==filesSignature){filesSignature=fs;$('files').replaceChildren();for(const f of state.files||[]){const a=document.createElement('a');a.href='/api/files/'+encodeURIComponent(f.name);a.download=f.name;a.className='file-link';a.textContent='↓ '+f.name;$('files').append(a)}}if(state.browser_ready)browserLive();if(!busy&&layoutQueued)scheduleLayout();if(task?.url&&!addressURL)setAddress(task.last_url||task.url);syncDock();fitFrame();updateSendButton()}
function updateSendButton(){const stop=busy&&!$('instruction').value.trim();$('start').replaceChildren(icon(stop?'stop':'send'));$('start').setAttribute('aria-label',stop?'إيقاف مؤقت':'إرسال');$('start').title=stop?'إيقاف مؤقت':'إرسال';$('start').disabled=submitting||(!busy&&!$('instruction').value.trim())}
function syncDock(){$('browserCard').style.setProperty('--dock-height',$('form').parentElement.getBoundingClientRect().height+'px')}
function autosize(){$('instruction').style.height='44px';$('instruction').style.height=Math.min(Math.max(44,Math.min(112,(visualViewport?.height||innerHeight)*.25)),Math.max(44,$('instruction').scrollHeight))+'px';syncDock();updateSendButton()}
function closeTools(){$('tools').hidden=true;$('toolsOpen').setAttribute('aria-expanded','false')}
function beginEdit(message){if(!editing)beforeEdit={text:$('instruction').value,newTask:newTaskMode};editing=message.id;newTaskMode=false;$('instruction').value=message.content;$('editNotice').hidden=false;$('instruction').focus();autosize();saveComposerDraft()}
function cancelEdit(){editing=null;$('editNotice').hidden=true;$('instruction').value=beforeEdit?.text||'';newTaskMode=beforeEdit?.newTask||false;beforeEdit=null;autosize();saveComposerDraft()}
function clearComposer(){editing=null;beforeEdit=null;$('editNotice').hidden=true;$('instruction').value='';ComposerDraft.clear();autosize()}
$('instruction').addEventListener('input',()=>{autosize();saveComposerDraft()});$('cancelEdit').onclick=cancelEdit;
$('loginDialog').addEventListener('cancel',e=>e.preventDefault());$('loginForm').onsubmit=async e=>{e.preventDefault();try{const s=await api('login',{password:$('password').value});csrf=s.csrf;$('password').value='';await connect()}catch(err){$('loginError').textContent=err.message}};
$('form').onsubmit=async e=>{e.preventDefault();if(submitting)return;const text=$('instruction').value.trim();if(!text){if(busy){submitting=true;updateSendButton();try{await api('control/pause',{});render(await api('state'))}catch(err){toast(err.message)}finally{submitting=false;updateSendButton()}}return}submitting=true;try{updateSendButton();const initial=!lastState?.task||newTaskMode;if(!busy)await applyLayout();if(initial){let url=currentAddress();if(!url)url=text.match(/https?:\/\/[^\s]+/)?.[0]||'';await api('tasks',{url,instruction:text,allow_actions:$('allowActions').checked});addressDirty=false;if(url)setAddress(url);newTaskMode=false}else await api('messages',{text,edit_id:editing});clearComposer();$('browserCard').classList.remove('focus-mode');$('expand').setAttribute('aria-pressed','false');closeTools();render(await api('state'));ChatView.latest()}catch(err){toast(err.message)}finally{submitting=false;updateSendButton()}};
$('focusUrl').onclick=()=>{closeTools();$('url').focus()};$('newTask').onclick=()=>{if(busy)return toast('أوقف المهمة الحالية أولًا');clearComposer();newTaskMode=true;closeTools();$('instruction').focus()};
$('addressForm').onsubmit=async e=>{e.preventDefault();const url=currentAddress();if(!url)return;try{$('open').disabled=true;await applyLayout();await api('browser/open',{url});addressDirty=false;setAddress(url);$('url').blur();render(await api('state'))}catch(err){toast(err.message)}finally{$('open').disabled=busy}};
for(const [id,action] of [['takeover','pause'],['cancel','cancel'],['resume','resume'],['approve','approve']])$(id).onclick=async()=>{try{await api('control/'+action,{});closeTools();render(await api('state'))}catch(err){toast(err.message)}};
async function input(body){try{await api('browser/input',body)}catch(err){toast(err.message)}}
let pointer=null;$('screen').onpointerdown=e=>{pointer={x:e.clientX,y:e.clientY}};$('screen').onpointerup=e=>{if(!pointer)return;const origin=pointer;pointer=null;if(busy&&!manualVerification)return toast('استلم التحكم أولًا');const dx=e.clientX-origin.x,dy=e.clientY-origin.y,rect=e.target.getBoundingClientRect();if(Math.abs(dy)>25&&zoom===1){input({kind:'scroll',delta:-dy*viewport.height/rect.height});return}if(Math.abs(dx)>10||Math.abs(dy)>10)return;input({kind:'click',x:(e.clientX-rect.left)/rect.width*viewport.width,y:(e.clientY-rect.top)/rect.height*viewport.height})};$('screen').onpointercancel=()=>pointer=null;$('screen').addEventListener('wheel',e=>{if(!busy||manualVerification){e.preventDefault();input({kind:'scroll',delta:e.deltaY})}},{passive:false});
function setZoom(value){const view=$('viewport'),stage=$('browserStage');const center=(view.scrollLeft+view.clientWidth/2)/Math.max(1,stage.getBoundingClientRect().width);zoom=Math.max(1,Math.min(3,value));fitFrame();requestAnimationFrame(()=>view.scrollLeft=zoom===1?0:Math.max(0,center*stage.getBoundingClientRect().width-view.clientWidth/2));$('zoomLabel').textContent=zoom===1?'ملاءمة':Math.round(zoom*100)+'%';$('screen').style.touchAction=zoom===1?'none':'pan-x pan-y'}$('zoomIn').onclick=()=>setZoom(zoom+.5);$('zoomOut').onclick=()=>setZoom(zoom-.5);
$('expand').onclick=()=>{const focus=$('browserCard').classList.toggle('focus-mode');$('expand').setAttribute('aria-pressed',String(focus));closeTools();setZoom(1)};
function openHistory(){closeTools();if(!$('activityPanel').open)$('activityPanel').showModal();requestAnimationFrame(()=>$('activityPanel').scrollTop=$('activityPanel').scrollHeight)}$('activityOpen').onclick=openHistory;$('historyOpen').onclick=openHistory;$('activityClose').onclick=()=>$('activityPanel').close();
$('toolsOpen').onclick=()=>{const open=$('tools').hidden;$('tools').hidden=!open;$('toolsOpen').setAttribute('aria-expanded',String(open))};document.addEventListener('click',e=>{if(!$('tools').contains(e.target)&&!$('toolsOpen').contains(e.target))closeTools()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeTools()});
$('keyboardOpen').onclick=()=>{closeTools();$('keyboard').showModal()};$('keyboardClose').onclick=()=>$('keyboard').close();for(const el of document.querySelectorAll('[data-key]'))el.onclick=()=>input({kind:'key',key:el.dataset.key});for(const el of document.querySelectorAll('[data-scroll]'))el.onclick=()=>input({kind:'scroll',delta:Number(el.dataset.scroll)});$('type').onclick=async()=>{const text=$('typing').value;$('typing').value='';await input({kind:'text',text})};$('typing').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();$('type').click()}};
$('settingsOpen').onclick=async()=>{closeTools();$('settings').showModal();loadModelSettings().catch(err=>toast(err.message));loadLimits().catch(err=>toast(err.message));try{const p=await api('proxy');$('proxyEnabled').checked=p.enabled;$('proxyScope').value=p.scope||'application';$('proxyUrl').value=p.url;$('proxyUsername').value=p.username;$('proxyPassword').value='';$('proxyResult').textContent=p.check?.ok?'عنوان خروج المتصفح: '+p.check.ip:''}catch(err){toast(err.message)}};$('settingsClose').onclick=()=>$('settings').close();
$('proxyForm').onsubmit=async e=>{e.preventDefault();try{$('proxySave').disabled=true;await api('proxy',{enabled:$('proxyEnabled').checked,scope:$('proxyScope').value,url:$('proxyUrl').value,username:$('proxyUsername').value,password:$('proxyPassword').value,keep_password:true},'PUT');$('proxyPassword').value='';$('proxyResult').textContent='تم الحفظ. المتصفح هيفتح بالاتصال الجديد.';render(await api('state'))}catch(err){$('proxyResult').textContent=err.message}finally{$('proxySave').disabled=false}};
$('proxyTest').onclick=async()=>{try{$('proxyTest').disabled=true;$('proxyResult').textContent='يفحص عنوان خروج المتصفح…';const r=await api('proxy/test',{});$('proxyResult').textContent='عنوان خروج المتصفح: '+r.ip;render(await api('state'))}catch(err){$('proxyResult').textContent=err.message}finally{$('proxyTest').disabled=false}};
let modelProfiles=null;
async function loadModelSettings(){modelProfiles=await api('model/settings');$('modelProvider').value=modelProfiles.active;showModelProfile()}
function showModelProfile(){const p=modelProfiles?.profiles[$('modelProvider').value]||{};$('modelName').value=p.model||'';$('modelContext').value=p.context_window||32768;$('priceInput').value=p.pricing?.input??'';$('priceOutput').value=p.pricing?.output??'';$('priceCached').value=p.pricing?.cached_input??'';$('priceSource').value=p.pricing?.source||'';$('modelBase').value=p.base_url||'';$('modelKey').value='';$('modelKey').placeholder=p.has_key?'محفوظ · اتركه فارغًا للاحتفاظ به':'مفتاح API';$('modelVision').checked=p.vision!==false;$('loadFreeModels').hidden=$('modelProvider').value!=='openrouter';$('modelResult').textContent='';$('freeModels').replaceChildren();$('providerHint').hidden=$('modelProvider').value!=='zai';$('chooseVisionModel').hidden=$('modelProvider').value!=='zai'}
function modelBody(){return {provider:$('modelProvider').value,model:$('modelName').value.trim(),base_url:$('modelBase').value.trim(),api_key:$('modelKey').value.trim(),vision:$('modelVision').checked,context_window:Number($('modelContext').value)||32768,pricing:readPricing()}}
$('modelProvider').onchange=showModelProfile;
$('modelForm').onsubmit=async e=>{e.preventDefault();$('saveModel').disabled=true;try{modelProfiles=await api('model/settings',modelBody(),'PUT');showModelProfile();const session=await api('session');$('model').textContent=session.provider+' / '+session.model;$('modelResult').textContent='تم الحفظ والاستخدام'}catch(err){$('modelResult').textContent=err.message}finally{$('saveModel').disabled=false}};
$('testModel').onclick=async()=>{try{$('testModel').disabled=true;$('modelResult').textContent='يختبر الرد المنظّم'+($('modelVision').checked?' والصور…':'…');const result=await api('model/test',modelBody());$('modelResult').textContent=result.browser?.installed===false?'اتصال الموديل نجح، لكن '+result.browser.message:'نجح اختبار الموديل · المتصفح مثبت · يمكنك الحفظ'}catch(err){$('modelResult').textContent=err.message}finally{$('testModel').disabled=false}};
$('deleteModel').onclick=async()=>{try{modelProfiles=await api('model/settings/'+$('modelProvider').value,undefined,'DELETE');$('modelProvider').value=modelProfiles.active;showModelProfile();const s=await api('session');$('model').textContent=s.provider+' / '+s.model;$('modelResult').textContent='تم حذف الإعداد المحفوظ'}catch(err){$('modelResult').textContent=err.message}};
$('loadFreeModels').onclick=async()=>{try{$('loadFreeModels').disabled=true;const data=await api('model/catalog');$('freeModels').replaceChildren(...data.models.map(m=>{const o=document.createElement('option');o.value=m.id;o.label=m.vision?'يدعم الصور':'نصي';return o}));$('modelResult').textContent=data.models.length+' موديل مجاني حاليًا · الاختيار من حقل الموديل'}catch(err){$('modelResult').textContent=err.message}finally{$('loadFreeModels').disabled=false}};
$('settings').addEventListener('close',()=>{$('modelKey').value='';$('proxyPassword').value=''});

$('clear').onclick=async()=>{if(!confirm('مسح جلسات المواقع المحفوظة؟'))return;try{await api('browser/clear',{});toast('تم مسح الجلسات');render(await api('state'))}catch(err){toast(err.message)}};$('logout').onclick=async()=>{await api('logout',{});ComposerDraft.clear();clearComposer();draftRestored=false;$('settings').close();showLogin()};
document.addEventListener('visibilitychange',()=>{if(document.hidden){saveComposerDraft();clearTimeout(reconnectTimer);if(live){live.onclose=null;live.close();live=null}if(stream){stream.close();stream=null}viewConnected=false;stateConnected=false}else if(authenticated){events();browserLive();api('state').then(render).catch(err=>toast(err.message));tickPhase()}});
async function applyLayout(){if(layoutPromise)return layoutPromise;if(!authenticated||busy||!layoutQueued)return;const height=Math.max(800,Math.min(2200,Math.round(browserDisplayHeight/Math.max(1,$('viewport').clientWidth)*1280)));if(Math.abs(height-viewport.height)<50){layoutQueued=false;return;}layoutPending=true;layoutPromise=(async()=>{viewport=await api('browser/layout',{height});layoutQueued=false;fitFrame()})().finally(()=>{layoutPending=false;layoutPromise=null});return layoutPromise}
function scheduleLayout(){if(!authenticated||busy||layoutPending||!layoutQueued)return;clearTimeout(layoutTimer);layoutTimer=setTimeout(()=>applyLayout().catch(()=>console.debug('Layout deferred')),180)}
let viewportBaseline=window.innerHeight,baselineWidth=window.innerWidth,browserDisplayHeight=320;
function syncViewport(){const vv=window.visualViewport;const height=vv?.height||window.innerHeight;const width=window.innerWidth;const editingField=/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName||'');if(Math.abs(width-baselineWidth)>60){viewportBaseline=window.innerHeight;baselineWidth=width}const keyboard=editingField&&height<viewportBaseline-120;document.body.classList.toggle('keyboard-open',keyboard);document.body.classList.toggle('compact-keyboard',keyboard&&height<480);document.documentElement.style.setProperty('--app-height',height+'px');document.documentElement.style.setProperty('--visual-top',(vv?.offsetTop||0)+'px');if(!keyboard){viewportBaseline=Math.max(height,window.innerHeight);const next=Math.round(Math.max(240,Math.min(360,(viewportBaseline-44)*.4)));if(next!==browserDisplayHeight){browserDisplayHeight=next;layoutQueued=true}document.documentElement.style.setProperty('--browser-display-height',browserDisplayHeight+'px');scheduleLayout()}syncDock();fitFrame()}
if(window.visualViewport){window.visualViewport.addEventListener('resize',syncViewport);window.visualViewport.addEventListener('scroll',syncViewport)}window.addEventListener('resize',syncViewport);document.addEventListener('focusin',syncViewport);document.addEventListener('focusout',()=>requestAnimationFrame(syncViewport));new ResizeObserver(()=>{syncDock();fitFrame()}).observe($('form').parentElement);syncViewport();setZoom(1);setInterval(tickPhase,1000);connect().catch(err=>{showLogin();$('loginError').textContent=err.message});if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js',{scope:'/'}).catch(()=>{});

$('proxyUrl').addEventListener('input',()=>{const v=$('proxyUrl').value;if(v.includes('@')||(!v.includes('://')&&v.split(':').length>=4)){$('proxyUsername').value='';$('proxyPassword').value=''}});

$('verificationFocus').onclick=()=>{const focus=$('browserCard').classList.toggle('focus-mode');$('expand').setAttribute('aria-pressed',String(focus));setZoom(focus?1.5:1)};

$('chooseVisionModel').onclick=()=>{if($('modelName').value!=='glm-4.6v-flash')clearModelMetadata();$('modelName').value='glm-4.6v-flash';$('modelVision').checked=true;$('modelResult').textContent='تم اختيار موديل الرؤية؛ اختبر ثم احفظ لاستخدامه'};

function optionalNumber(id){const v=$(id).value.trim();return v===''?null:Number(v)}
function readPricing(){const input=optionalNumber('priceInput'),output=optionalNumber('priceOutput');if(input===null&&output===null)return null;if(input===null||output===null)throw Error('أدخل سعري الإدخال والإخراج أو اتركهما فارغين');return {input,output,cached_input:optionalNumber('priceCached'),source:$('priceSource').value.trim()||'user',checked_at:new Date().toISOString().slice(0,10)}}
function renderUsage(u){if(!u||!u.calls){$('usageSummary').textContent='لا طلبات مسجلة في هذه النسخة';return}const f=n=>Number(n).toLocaleString('ar-EG');const parts=[f(u.calls)+' طلب',f(u.total_tokens)+' توكن مُبلّغ',f(u.cached_tokens)+' مخزّن'];if(u.unknown_calls)parts.push(f(u.unknown_calls)+' طلب باستهلاك غير متاح');if(u.estimated_cost_usd!==null)parts.push('≈ $'+u.estimated_cost_usd.toFixed(6));else parts.push('التكلفة الكاملة غير متاحة'+(u.priced_calls?' · جزء معلوم ≈ $'+u.known_cost_usd.toFixed(6):''));const latest=u.recent?.at(-1);if(Number.isFinite(latest?.elapsed_ms))parts.push('آخر طلب '+f((latest.elapsed_ms/1000).toFixed(1))+' ث');$('usageSummary').textContent=parts.join(' · ')}
async function loadLimits(){const s=await api('task/settings');const p=lastState?.task&&['paused','failed'].includes(lastState.task.status)?s.current||s.defaults:s.defaults;$('tokenLimit').value=p.token_limit??'';$('costLimit').value=p.cost_limit_usd??'';$('limitsResult').textContent=''}
$('limitsForm').onsubmit=async e=>{e.preventDefault();$('saveLimits').disabled=true;try{await api('task/settings',{token_limit:optionalNumber('tokenLimit'),cost_limit_usd:optionalNumber('costLimit')},'PUT');$('limitsResult').textContent='تم الحفظ';render(await api('state'))}catch(err){$('limitsResult').textContent=err.message}finally{$('saveLimits').disabled=false}};

function clearModelMetadata(){for(const id of ['priceInput','priceOutput','priceCached','priceSource'])$(id).value='';$('modelContext').value=32768}
$('modelName').addEventListener('input',clearModelMetadata);

function saveComposerDraft(){if(!authenticated||!draftRestored)return;ComposerDraft.save({text:$('instruction').value,taskId:newTaskMode?null:lastState?.task?.id||null,editId:editing,newTask:newTaskMode})}
function restoreComposerDraft(task){if(draftRestored||!authenticated)return;draftRestored=true;const d=ComposerDraft.load();if(!d)return;if(!d.newTask&&d.taskId!==(task?.id||null)){ComposerDraft.clear();return}if(d.editId&&!task?.messages?.some(m=>m.id===d.editId&&m.role==='user')){ComposerDraft.clear();return}if($('instruction').value)return;$('instruction').value=d.text;editing=d.editId;newTaskMode=d.newTask;$('editNotice').hidden=!editing;autosize()}
window.addEventListener('pagehide',saveComposerDraft);
$('instruction').addEventListener('keydown',e=>{if(e.isComposing)return;if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('form').requestSubmit()}else if(e.key==='Escape'&&editing){e.preventDefault();cancelEdit()}});

let historyTask=null,historyRows=new Map(),replayKey=null,replayPump=null;
function syncHistory(task,replay){const id=task?.id||null;if(historyTask!==id){historyTask=id;historyRows.clear();replayKey=null}for(const e of task?.events||[])historyRows.set(e.seq,e);for(const e of replay?.events||[])historyRows.set(e.seq,e);const rows=[...historyRows.values()].sort((a,b)=>a.seq-b.seq);while(rows.length>2000)historyRows.delete(rows.shift().seq);$('loadOlderEvents').hidden=!rows.length||rows[0].seq<=1||rows.length>=2000;return rows}
function queueReplay(task,replay){
 if(!task?.id||!replay?.has_more||!Number.isSafeInteger(replay.next_after))return;
 const end=task.event_seq||Math.max(0,...(task.events||[]).map(e=>e.seq));
 const key=task.id+':'+replay.next_after+':'+end;if(replayPump||replayKey===key||end<=replay.next_after)return;
 replayKey=key;const id=task.id;let after=Math.max(replay.next_after,end-2000);
 replayPump=(async()=>{
  try{
   while(historyTask===id&&after<end){
    const page=await api('tasks/'+encodeURIComponent(id)+'/events?after='+after+'&limit=500');
    if(historyTask!==id)return;
    const events=(page.events||[]).filter(e=>Number.isSafeInteger(e.seq)&&e.seq>after&&e.seq<=end);
    if(!events.length)break;
    for(const e of events)historyRows.set(e.seq,e);
    const next=Math.max(...events.map(e=>e.seq));if(next<=after)break;after=next;
    if(lastState?.task?.id===id)render(lastState);
    if(!page.has_more)break;
   }
  }catch{if(historyTask===id){replayKey=null;toast('تعذر تحميل بعض الخطوات؛ افتح السجل للمراجعة')}}
  finally{replayPump=null;if(lastState?.task?.id!==id)queueReplay(lastState?.task,lastState?.replay)}
 })();
}
$('loadOlderEvents').onclick=async()=>{const id=historyTask;const before=Math.min(...historyRows.keys());$('loadOlderEvents').disabled=true;try{const r=await api('tasks/'+encodeURIComponent(id)+'/events?before='+before+'&limit=200');if(historyTask!==id)return;for(const e of r.events)historyRows.set(e.seq,e);renderEvents(syncHistory(lastState.task));}catch(err){toast(err.message)}finally{$('loadOlderEvents').disabled=false}};

let messageHistoryTask=null,messageHistoryRows=new Map(),messagesReachedStart=false;
function syncMessageHistory(task,meta){if(messageHistoryTask!==task?.id){messageHistoryTask=task?.id;messageHistoryRows.clear();messagesReachedStart=false}for(const [id,m] of messageHistoryRows)messageHistoryRows.set(id,{...m,read_only:true});for(const m of task?.messages||[])messageHistoryRows.set(m.id,{...m,read_only:false});const rows=[...messageHistoryRows.values()].sort((a,b)=>(a.archive_cursor||0)-(b.archive_cursor||0));while(rows.length>250)messageHistoryRows.delete(rows.shift().id);$('loadOlderMessages').hidden=!meta?.has_more||messagesReachedStart||rows.length>=250;return rows}
$('loadOlderMessages').onclick=async()=>{const id=messageHistoryTask;const cursors=[...messageHistoryRows.values()].map(m=>m.archive_cursor).filter(Number.isFinite);if(!cursors.length)return;$('loadOlderMessages').disabled=true;try{const r=await api('tasks/'+encodeURIComponent(id)+'/messages?before='+Math.min(...cursors)+'&limit=50');if(messageHistoryTask!==id)return;for(const m of r.messages)messageHistoryRows.set(m.id,{...m,read_only:true});if(!r.has_more)messagesReachedStart=true;render(lastState)}catch(err){toast(err.message)}finally{$('loadOlderMessages').disabled=false}};
