"""Offline/online SQLite backup and non-destructive legacy export. Never replaces live data."""
import argparse,json,os,sqlite3
from pathlib import Path
from urllib.parse import quote

def open_source(source):
    return sqlite3.connect('file:'+quote(str(Path(source).resolve()),safe='/')+'?mode=ro',uri=True,timeout=5)

def reserve(source,output):
    source=Path(source).resolve();output=Path(output).resolve()
    if source==output:raise ValueError('Output must differ from the live database')
    if not source.is_file():raise ValueError('Source database does not exist')
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
    return source,output

def backup(source,output):
    source,output=reserve(source,output)
    try:
        original=open_source(source);destination=sqlite3.connect(output)
        try:
            original.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup integrity check failed')
        finally:destination.close();original.close()
    except BaseException:
        output.unlink(missing_ok=True);raise
    return {'mode':'backup','integrity':'ok'}

def export_legacy(source,output):
    source,output=reserve(source,output);count=0
    try:
        original=open_source(source);destination=sqlite3.connect(output)
        try:
            original.execute('BEGIN')
            tables={r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            with destination:
                destination.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,updated REAL,data TEXT)')
                for task_id,updated,raw in original.execute('SELECT id,updated,data FROM tasks'):
                    data=json.loads(raw)
                    if 'task_events' in tables:
                        rows=original.execute('SELECT data FROM task_events WHERE task_id=? ORDER BY seq DESC LIMIT 200',(task_id,)).fetchall()
                        if rows:data['events']=[json.loads(r[0]) for r in reversed(rows)]
                    if 'task_messages' in tables:
                        rows=original.execute('SELECT data FROM task_messages WHERE task_id=? ORDER BY row_id DESC LIMIT 50',(task_id,)).fetchall()
                        if rows:data['messages']=[json.loads(r[0]) for r in reversed(rows)]
                    destination.execute('INSERT INTO tasks VALUES(?,?,?)',(task_id,updated,json.dumps(data,ensure_ascii=False)));count+=1
            if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Export integrity check failed')
        finally:destination.close();original.close()
    except BaseException:
        output.unlink(missing_ok=True);raise
    return {'mode':'legacy-export','tasks':count,'integrity':'ok','note':'Latest 200 events/50 messages per task; retain a full v7.5 backup for the entire archive.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['backup','legacy-export']);parser.add_argument('--source',default=os.path.join(os.getenv('DATA_DIR','/data'),'tasks.sqlite3'));parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:print(json.dumps((backup if args.mode=='backup' else export_legacy)(args.source,args.output)))
    except (OSError,sqlite3.Error,ValueError) as exc:
        parser.exit(1,'Operation failed ('+type(exc).__name__+'). Check source, permissions and a new output filename; live data was not replaced.\n')
