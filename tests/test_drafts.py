"""Draft expiry/corruption/privacy guards; Node is a test-only optional runtime."""
import json,shutil,subprocess
from pathlib import Path
import pytest
NODE=shutil.which('node')
pytestmark=pytest.mark.skipif(not NODE,reason='Node is optional for these frontend unit checks')
SOURCE=Path(__file__).resolve().parents[1]/'static/drafts.js'
def run(body):
    harness='''const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let stored=null;const sessionStorage={getItem:()=>stored,setItem:(k,v)=>stored=v,removeItem:()=>stored=null};
let clock=Date.now();const sandbox={sessionStorage,Date,assert};Date.now=()=>clock;
const source=fs.readFileSync(process.argv[1],'utf8');
vm.runInNewContext(source+'\\n'+process.argv[2],sandbox);
'''
    subprocess.run([NODE,'-e',harness,str(SOURCE),body],check=True,capture_output=True,text=True)

def test_draft_roundtrip_expiry_and_malformed_storage():
    run("""
const d={text:'مسودة عادية',taskId:'task-1',editId:null,newTask:false};
ComposerDraft.save(d);assert.equal(ComposerDraft.load().text,d.text);
const raw=JSON.parse(sessionStorage.getItem('x'));raw.savedAt=Date.now()-9*60*60*1000;sessionStorage.setItem('x',JSON.stringify(raw));
assert.equal(ComposerDraft.load(),null);assert.equal(sessionStorage.getItem('x'),null);
sessionStorage.setItem('x','not JSON');assert.equal(ComposerDraft.load(),null);
""")

def test_draft_skips_known_credentials_and_proxy_lines():
    run("""
for(const text of ['sk-'+'a'.repeat(30),'a'.repeat(32)+'.'+'B'.repeat(16),'password=fixture-only','http://owner:fixture@proxy.example:8080','1.2.3.4:8080:owner:fixture']){
 ComposerDraft.save({text,taskId:null,editId:null,newTask:true});assert.equal(ComposerDraft.load(),null);
}
ComposerDraft.save({text:'ابحث عن معنى كلمة password',taskId:null,editId:null,newTask:true});
assert.notEqual(ComposerDraft.load(),null);
""")

def test_disabled_storage_does_not_break_composer():
    run("""
sessionStorage.getItem=()=>{throw Error('disabled')};sessionStorage.setItem=()=>{throw Error('disabled')};sessionStorage.removeItem=()=>{throw Error('disabled')};
ComposerDraft.save({text:'normal',taskId:null,editId:null,newTask:true});assert.equal(ComposerDraft.load(),null);ComposerDraft.clear();
""")
