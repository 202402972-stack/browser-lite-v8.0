"""Fixed editor operations over CDP. No shell or caller-supplied JavaScript."""
import json,asyncio
from browser_use.agent.views import ActionResult
EDITOR_SCRIPT=r'''(code,selector,write)=>{
 const visible=e=>e&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 // Monaco often inserts its editor node inside the caller-selected container.
 // Multiple matching editors are still rejected below rather than guessing.
 const matches=e=>!selector||e.matches(selector)||!!e.querySelector(selector)||!!e.closest(selector);
 const candidates=[];
 for(const e of (window.monaco?.editor?.getEditors?.()||[])){
  const dom=e.getDomNode();if(visible(dom)&&matches(dom)&&e.getModel())candidates.push({kind:'monaco',read:()=>e.getValue(),write:v=>{if(e.getRawOptions?.().readOnly)throw Error('read-only');e.executeEdits('dot',[{range:e.getModel().getFullModelRange(),text:v,forceMoveMarkers:true}]);e.pushUndoStop()}})
 }
 for(const dom of document.querySelectorAll('.CodeMirror'))if(visible(dom)&&matches(dom)&&dom.CodeMirror)candidates.push({kind:'codemirror5',read:()=>dom.CodeMirror.getValue(),write:v=>{if(dom.CodeMirror.getOption('readOnly'))throw Error('read-only');dom.CodeMirror.setValue(v)}});
 for(const dom of document.querySelectorAll('.ace_editor'))if(visible(dom)&&matches(dom)&&window.ace?.edit){const e=window.ace.edit(dom);candidates.push({kind:'ace',read:()=>e.getValue(),write:v=>{if(e.getReadOnly())throw Error('read-only');e.setValue(v,-1)}})}
 for(const dom of document.querySelectorAll('textarea'))if(visible(dom)&&matches(dom)&&!dom.closest('.monaco-editor,.CodeMirror,.ace_editor'))candidates.push({kind:'textarea',read:()=>dom.value,write:v=>{if(dom.readOnly||dom.disabled)throw Error('read-only');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(dom,v);dom.dispatchEvent(new Event('input',{bubbles:true}));dom.dispatchEvent(new Event('change',{bubbles:true}))}});
 if(candidates.length!==1)return {error:candidates.length?'Multiple editors: supply a more specific CSS selector.':'No supported visible editor found. Use indexed browser input for other editors.'};
 const e=candidates[0];if(write===true)e.write(code);const value=e.read();
 return write?{kind:e.kind,characters:value.length,matches:value===code}:{kind:e.kind,code:value.slice(0,24000),truncated:value.length>24000};
}'''
async def editor_operation(engine,code='',selector='',write=False):
    if not engine.browser:return ActionResult(error='Open a page first')
    if len(code)>60000:return ActionResult(error='Code exceeds 60000 characters')
    try:
        session=await engine.browser.get_or_create_cdp_session()
        expression='('+EDITOR_SCRIPT+')('+','.join(json.dumps(v) for v in (code,selector,write))+')'
        result=await session.cdp_client.send.Runtime.evaluate(params={'expression':expression,'returnByValue':True},session_id=session.session_id)
        if result.get('exceptionDetails'):return ActionResult(error='Editor rejected the operation; inspect selector and read-only state')
        value=result.get('result',{}).get('value') or {}
        if write and value.get('matches'):
            await asyncio.sleep(.15)
            verify='('+EDITOR_SCRIPT+')('+','.join(json.dumps(v) for v in (code,selector,'check'))+')'
            checked=await session.cdp_client.send.Runtime.evaluate(params={'expression':verify,'returnByValue':True},session_id=session.session_id)
            value=checked.get('result',{}).get('value') or {}
        if value.get('error'):return ActionResult(error=value['error'])
        if write and not value.get('matches'):return ActionResult(error='Editor value did not match; inspect the current editor before retrying')
        return ActionResult(extracted_content=json.dumps(value,ensure_ascii=False))
    except Exception:return ActionResult(error='Editor is unavailable; inspect the page again')
def register_editor_tools(tools,engine):
    @tools.action('Read code from exactly one visible Monaco, CodeMirror 5, Ace or textarea editor. Supply CSS selector if ambiguous. Other editor types should use normal indexed browser input.')
    async def read_editor(selector:str=''):
        return await editor_operation(engine,selector=selector)
    @tools.action('Replace code in the selected in-page editor. This edits website content only; does not execute server code. Verify using website output after the requested Run/Test action.')
    async def write_editor(code:str,selector:str=''):
        return await editor_operation(engine,code,selector,True)
