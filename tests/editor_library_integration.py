"""Optional real editor-library integration; downloads pinned test assets only."""
import hashlib, json, urllib.request
from playwright.sync_api import Error, sync_playwright
from editor_tools import EDITOR_SCRIPT

ASSETS = {
    'ace': ('https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js', 'd501268416cea35288e8dd07052907ff56340a00b2e26de86fc5595251e7e37c'),
    'codemirror': ('https://cdn.jsdelivr.net/npm/codemirror@5.65.20/lib/codemirror.js', '8e8b5e3cc4be7530a9b6b624bce95ff966cd667283005a103739fe37d3bdd97c'),
}
def asset(name):
    url, expected = ASSETS[name]
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(2_000_000)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('test asset integrity mismatch')
    return data.decode('utf-8')

def main():
    scripts = {name: asset(name) for name in ASSETS}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        operation = '(args)=>(' + EDITOR_SCRIPT + ')(...args)'
        def call(code='', selector='', write=False):
            return page.evaluate(operation, [code, selector, write])
        try:
            page.set_content('<div id="editor" style="width:500px;height:220px"></div>')
            page.add_script_tag(content=scripts['ace'])
            page.evaluate("window.editor=ace.edit('editor'); editor.session.setUseWorker(false); editor.setValue('before',-1)")
            assert call(selector='#editor')['code'] == 'before'
            assert call('after', '#editor', True)['matches']
            page.evaluate('editor.setReadOnly(true)')
            try: call('blocked', '#editor', True)
            except Error as exc: assert 'read-only' in str(exc)
            else: raise AssertionError('read-only Ace allowed write')
            assert call(selector='#editor')['code'] == 'after'
            page.set_content('<textarea id="source"></textarea>')
            page.add_script_tag(content=scripts['codemirror'])
            page.evaluate("window.editor=CodeMirror.fromTextArea(document.querySelector('#source')); editor.setValue('before')")
            assert call(selector='.CodeMirror')['code'] == 'before'
            assert call('after', '.CodeMirror', True)['matches']
            page.evaluate("editor.setOption('readOnly',true)")
            try: call('blocked', '.CodeMirror', True)
            except Error as exc: assert 'read-only' in str(exc)
            else: raise AssertionError('read-only CodeMirror allowed write')
            assert call(selector='.CodeMirror')['code'] == 'after'
            print(json.dumps({'ace':'1.43.3','codemirror':'5.65.20','read_write_and_readonly':'passed'}))
        finally: browser.close()
if __name__ == '__main__': main()
