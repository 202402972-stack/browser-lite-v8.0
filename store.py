import json, sqlite3, time, threading, os, tempfile
from pathlib import Path
class StoreUnavailable(RuntimeError):pass
class SecretUnavailable(RuntimeError):pass

class Store:
    def __init__(self, directory):
        self.root=Path(directory)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=threading.RLock();self.last_error=None
        self.db=sqlite3.connect(self.root/'tasks.sqlite3',check_same_thread=False,timeout=5)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, updated REAL, data TEXT)')
        self.db.commit()
        self._migrate()
    def _migrate(self):
        if self.db.execute('PRAGMA user_version').fetchone()[0]>=1:return
        has_rows=self.db.execute('SELECT 1 FROM tasks LIMIT 1').fetchone()
        backup=self.root/'tasks.pre-v75.sqlite3'
        if has_rows and not backup.exists():
            fd,temporary=tempfile.mkstemp(prefix='.migration-',suffix='.sqlite3',dir=self.root);os.close(fd)
            try:
                destination=sqlite3.connect(temporary)
                try:
                    self.db.backup(destination)
                    if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise StoreUnavailable('فشل التحقق من النسخة الاحتياطية')
                finally:destination.close()
                os.replace(temporary,backup)
            finally:
                if os.path.exists(temporary):os.unlink(temporary)
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS task_events(task_id TEXT NOT NULL,seq INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(task_id,seq))')
            self.db.execute('CREATE TABLE IF NOT EXISTS task_messages(row_id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,message_id TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(task_id,message_id))')
            self.db.execute('CREATE INDEX IF NOT EXISTS task_messages_page ON task_messages(task_id,row_id)')
            self.db.execute('CREATE TABLE IF NOT EXISTS service_meta(key TEXT PRIMARY KEY,value INTEGER NOT NULL)')
            self.db.execute("INSERT OR IGNORE INTO service_meta VALUES('revision',0)")
            for task_id,raw in self.db.execute('SELECT id,data FROM tasks'):
                data=json.loads(raw);self._archive(task_id,data)
            self.db.execute('PRAGMA user_version=1')
    def _archive(self,task_id,task):
        self.db.executemany('INSERT OR IGNORE INTO task_events VALUES(?,?,?)',[(task_id,e['seq'],json.dumps(e,ensure_ascii=False)) for e in task.get('events',[])])
        self.db.executemany('INSERT INTO task_messages(task_id,message_id,data) VALUES(?,?,?) ON CONFLICT(task_id,message_id) DO UPDATE SET data=excluded.data WHERE task_messages.data!=excluded.data',[(task_id,m['id'],json.dumps(m,ensure_ascii=False)) for m in task.get('messages',[])])
    def save(self, task):
        try:
            with self.lock,self.db:
                self.db.execute("UPDATE service_meta SET value=value+1 WHERE key='revision'")
                revision=self.db.execute("SELECT value FROM service_meta WHERE key='revision'").fetchone()[0]
                payload={k:v for k,v in task.items() if k not in ('events','messages')}
                payload['_revision']=revision
                self.db.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?)',(task['id'],time.time(),json.dumps(payload,ensure_ascii=False)))
                self._archive(task['id'],task)
            task['_revision']=revision;self.last_error=None
            return revision
        except sqlite3.Error:
            self.last_error='STORAGE_WRITE_FAILED'
            raise StoreUnavailable('تعذر حفظ التقدم؛ راجع مساحة القرص وصلاحيات الـVolume') from None
    def _hydrate(self,row):
        if not row:return None
        data=json.loads(row[0]);task_id=data['id']
        events=self.db.execute('SELECT data FROM task_events WHERE task_id=? ORDER BY seq DESC LIMIT 200',(task_id,)).fetchall()
        messages=self.db.execute('SELECT data FROM task_messages WHERE task_id=? ORDER BY row_id DESC LIMIT 50',(task_id,)).fetchall()
        if events:data['events']=[json.loads(r[0]) for r in reversed(events)]
        if messages:data['messages']=[json.loads(r[0]) for r in reversed(messages)]
        return data
    def latest(self):
        with self.lock:return self._hydrate(self.db.execute('SELECT data FROM tasks ORDER BY updated DESC LIMIT 1').fetchone())
    def history(self):
        with self.lock:return [self._hydrate(r) for r in self.db.execute('SELECT data FROM tasks ORDER BY updated DESC LIMIT 20').fetchall()]
    def get(self,task_id):
        with self.lock:return self._hydrate(self.db.execute('SELECT data FROM tasks WHERE id=?',(task_id,)).fetchone())
    def events(self,task_id,after=0,before=None,limit=100):
        limit=max(1,min(500,limit));params=[task_id,after];where='task_id=? AND seq>?'
        if before is not None:where+=' AND seq<?';params.append(before)
        with self.lock:
            rows=self.db.execute('SELECT data FROM task_events WHERE '+where+' ORDER BY seq '+('DESC' if before is not None else 'ASC')+' LIMIT ?',(*params,limit+1)).fetchall()
        events=[json.loads(r[0]) for r in rows[:limit]]
        if before is not None:events.reverse()
        return {'events':events,'has_more':len(rows)>limit,'next_after':events[-1]['seq'] if events else after,'next_before':events[0]['seq'] if events else before}
    def messages(self,task_id,before=None,limit=50):
        where='task_id=?';params=[task_id];limit=max(1,min(100,limit))
        if before is not None:where+=' AND row_id<?';params.append(before)
        with self.lock:rows=self.db.execute('SELECT row_id,data FROM task_messages WHERE '+where+' ORDER BY row_id DESC LIMIT ?',(*params,limit+1)).fetchall()
        return {'messages':[dict(json.loads(r[1]),archive_cursor=r[0]) for r in reversed(rows[:limit])],'has_more':len(rows)>limit,'next_before':rows[min(limit,len(rows))-1][0] if rows else None}
    def probe(self):
        try:
            with self.lock,self.db:
                self.db.execute("INSERT INTO service_meta VALUES('heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(int(time.time()),))
            self.last_error=None;return True
        except sqlite3.Error:self.last_error='STORAGE_WRITE_FAILED';return False
    def secret(self,name):
        from cryptography.fernet import InvalidToken
        path=self.root/(name+'.enc')
        if not path.exists():return None
        try:return json.loads(self._cipher().decrypt(path.read_bytes()))
        except (InvalidToken,ValueError,UnicodeError,OSError):
            raise SecretUnavailable('تعذر فتح الإعدادات المشفرة. استعد مفتاح التشفير والـVolume من النسخة الاحتياطية.') from None
    def _cipher(self):
        from cryptography.fernet import Fernet
        import os
        path=self.root/'settings.key'
        key=os.getenv('SETTINGS_ENCRYPTION_KEY')
        if not key:
            if not path.exists():
                # Never generate a new, incompatible key over existing encrypted data.
                if any(self.root.glob('*.enc')):
                    raise SecretUnavailable('مفتاح الإعدادات المشفرة مفقود. استعده من النسخة الاحتياطية.')
                fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
            key=path.read_bytes()
        try:return Fernet(key)
        except (ValueError,TypeError):
            raise SecretUnavailable('مفتاح الإعدادات المشفرة غير صالح. راجع مفتاح التشفير.') from None
    def save_secret(self,name,data):
        import os,tempfile
        with self.lock:
            try:
                path=self.root/(name+'.enc')
                payload=self._cipher().encrypt(json.dumps(data).encode())
                fd,temporary=tempfile.mkstemp(prefix='.secret-',dir=self.root)
                try:
                    with os.fdopen(fd,'wb') as f:
                        f.write(payload);f.flush();os.fsync(f.fileno())
                    os.replace(temporary,path)
                finally:
                    if os.path.exists(temporary):os.unlink(temporary)
            except OSError:
                raise SecretUnavailable('تعذر حفظ الإعدادات. راجع مساحة وصلاحيات الـVolume.') from None
