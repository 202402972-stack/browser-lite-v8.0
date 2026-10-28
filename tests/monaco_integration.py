"""Exercise the adapter with a pinned real Monaco build in disposable Chromium."""
import base64, functools, hashlib, http.server, io, json, tarfile, tempfile, threading, urllib.request
from pathlib import Path
from playwright.sync_api import Error, sync_playwright
from editor_tools import EDITOR_SCRIPT

URL='https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.2.tgz'
INTEGRITY='GEQWEZmfkOGLdd3XK8ryrfWz3AIP8YymVXiPHEdewrUq7mh0qrKrfHLNCXcbB6sTnMLnOZ3ztSiKcciFUkIJwQ=='

def main():
 with urllib.request.urlopen(URL, timeout=60) as response:
  blob=response.read(25_000_001)
 assert len(blob)<=25_000_000 and base64.b64encode(hashlib.sha512(blob).digest()).decode()==INTEGRITY
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp)
  with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
   for member in archive:
    prefix='package/min/vs/'
    if not member.isfile() or not member.name.startswith(prefix):continue
    relative=Path(member.name[len('package/min/'):])
    target=(root/relative).resolve()
    if not target.is_relative_to(root.resolve()):raise ValueError('Invalid archive path')
    target.parent.mkdir(parents=True,exist_ok=True)
    with archive.extractfile(member) as source, target.open('wb') as output:
     output.write(source.read())
  (root/'index.html').write_text('<!doctype html><div id="editor" style="width:600px;height:300px"></div><script src="/vs/loader.js"></script>')
  handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=tmp)
  class Quiet(handler.func):
   def log_message(self,*args):pass
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=tmp))
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page()
    page.goto('http://127.0.0.1:'+str(server.server_port)+'/')
    page.evaluate("require.config({paths:{vs:'/vs'}}); require(['vs/editor/editor.main'],()=>{window.editor=monaco.editor.create(document.getElementById('editor'),{value:'before',language:'javascript'});window.loaded=true})")
    page.wait_for_function('window.loaded===true',timeout=30000)
    operation='(args)=>('+EDITOR_SCRIPT+')( ...args)'
    def call(code='',selector='#editor',write=False):return page.evaluate(operation,[code,selector,write])
    assert call()['code']=='before'
    assert call('after',write=True)['matches']
    page.evaluate('editor.updateOptions({readOnly:true})')
    try:call('blocked',write=True)
    except Error as exc:assert 'read-only' in str(exc)
    else:raise AssertionError('read-only Monaco allowed write')
    assert call()['code']=='after'
    page.evaluate("const el=document.createElement('div');el.style='width:600px;height:200px';document.body.appendChild(el);window.second=monaco.editor.create(el,{value:'other'})")
    assert 'Multiple editors' in call(selector='body')['error']
    assert page.evaluate('second.getValue()')=='other'
    browser.close()
    print(json.dumps({'monaco':'0.52.2','read_write_readonly_and_ambiguous':'passed'}))
  finally:
   server.shutdown();server.server_close()
if __name__=='__main__':main()
