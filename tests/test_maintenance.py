import json,sqlite3
import pytest
from store import Store
from maintenance import backup,export_legacy

def test_consistent_backup_and_legacy_export_preserve_live_database(tmp_path):
    store=Store(tmp_path/'live')
    task={'id':'live','status':'paused','events':[{'seq':n,'title':str(n)} for n in range(1,251)],'messages':[{'id':str(n),'role':'user','content':str(n)} for n in range(1,61)]}
    store.save(task);source=store.root/'tasks.sqlite3'
    full=tmp_path/'full.sqlite3';legacy=tmp_path/'legacy.sqlite3'
    assert backup(source,full)['integrity']=='ok'
    full_db=sqlite3.connect(full)
    assert full_db.execute('SELECT count(*) FROM task_events').fetchone()[0]==250
    full_db.close()
    assert export_legacy(source,legacy)['tasks']==1
    old=sqlite3.connect(legacy)
    assert old.execute('PRAGMA user_version').fetchone()[0]==0
    data=json.loads(old.execute('SELECT data FROM tasks').fetchone()[0]);old.close()
    assert len(data['events'])==200 and len(data['messages'])==50 and data['id']=='live'
    assert len(store.events('live',limit=500)['events'])==250
    with pytest.raises(FileExistsError):backup(source,full)
    with pytest.raises(ValueError):export_legacy(source,source)

def test_restore_includes_task_database_encrypted_settings_and_key(tmp_path,monkeypatch):
    import shutil
    monkeypatch.delenv('SETTINGS_ENCRYPTION_KEY',raising=False)
    store=Store(tmp_path/'live')
    store.save({'id':'restore-task','status':'paused','steps':7})
    store.save_secret('models',{'active':'fixture','profiles':{'fixture':{'api_key':'not-a-real-key'}}})
    store.save_secret('proxy',{'enabled':True,'server':{'host':'proxy.example'}})
    restored=tmp_path/'restored';restored.mkdir()
    backup(store.root/'tasks.sqlite3',restored/'tasks.sqlite3')
    for filename in ('settings.key','models.enc','proxy.enc'):
        shutil.copy2(store.root/filename,restored/filename)
    recovered=Store(restored)
    assert recovered.latest()['steps']==7
    assert recovered.secret('models')['active']=='fixture'
    assert recovered.secret('proxy')['server']['host']=='proxy.example'
