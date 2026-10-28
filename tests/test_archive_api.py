import asyncio,json
import pytest
from fastapi.testclient import TestClient
from store import Store
from engine import Engine

@pytest.fixture
def service(tmp_path,monkeypatch):
 import app
 storage=Store(tmp_path);e=Engine(storage)
 monkeypatch.setattr(app,'store',storage);monkeypatch.setattr(app,'engine',e)
 monkeypatch.setattr(app,'sessions',{});monkeypatch.setattr(app,'attempts',{})
 monkeypatch.setenv('APP_PASSWORD','archive-testing-password')
 with TestClient(app.app) as c:yield c,e,app

def auth(c):
 r=c.post('/api/login',json={'password':'archive-testing-password'},headers={'Origin':'http://testserver'});assert r.status_code==200
 c.headers.update({'Origin':'http://testserver','X-CSRF-Token':r.json()['csrf']})

def test_archive_api_auth_limits_pagination_and_readiness(service):
 c,e,app=service
 assert c.get('/api/tasks/archived/events').status_code==401
 auth(c);e.task={'id':'archived','status':'paused'}
 for n in range(240):e.event('reading',str(n))
 assert c.get('/api/tasks/archived/events?after=200&limit=20').json()['next_after']==220
 before=c.get('/api/tasks/archived/events?before=100&limit=10').json()
 assert [r['seq'] for r in before['events']]==list(range(90,100))
 assert c.get('/api/tasks/archived/events?limit=501').status_code==422
 for n in range(60):e.chat('user',str(n))
 snapshot=c.get('/api/state').json()
 assert snapshot['message_history']['has_more'] and len(snapshot['task']['messages'])==50
 assert snapshot['task']['messages'][0]['archive_cursor']>0
 assert c.get('/api/tasks/missing/messages').status_code==404
 assert c.get('/readyz').json()['ready']
 e.store.last_error='STORAGE_WRITE_FAILED'
 r=c.get('/readyz');assert r.status_code==503 and r.json()['code']=='STORAGE_WRITE_FAILED'
 e.store.last_error=None;e.closing=True
 assert c.get('/readyz').status_code==503

def test_sse_cursor_replays_gap_from_archive_without_duplicates(service,monkeypatch):
 c,e,app=service;auth(c);e.task={'id':'replay','status':'paused'}
 for n in range(240):e.event('reading',str(n))
 class Request:
  headers={'last-event-id':'replay:20:1'}
  async def is_disconnected(self):return False
 async def run():
  monkeypatch.setattr(app,'authenticate',lambda r:{})
  response=await app.events(Request());iterator=response.body_iterator
  first=await anext(iterator);await iterator.aclose()
  assert first.startswith('id: replay:240:')
  snapshot=json.loads(next(line[6:] for line in first.splitlines() if line.startswith('data: ')))
  assert [r['seq'] for r in snapshot['replay']['events']]==list(range(21,241))
  assert response.headers['x-accel-buffering']=='no'
  assert app.replay_for(snapshot,'broken') is None
  assert app.replay_for(snapshot,'wrong:1:1') is None
  Request.headers={};Request.query_params={'cursor':'replay:20:1'}
  response=await app.events(Request());iterator=response.body_iterator
  assert '"next_after": 240' in await anext(iterator)
  await iterator.aclose()
 asyncio.run(run())
