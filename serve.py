"""Uvicorn lifecycle hook: stop viewer streams before waiting for graceful shutdown."""
import os
from pathlib import Path
import uvicorn

class DotServer(uvicorn.Server):
    def __init__(self,config,engine):
        super().__init__(config);self.engine=engine
    def handle_exit(self,sig,frame):
        self.engine.closing=True
        super().handle_exit(sig,frame)

def run(application=None,engine=None,host='0.0.0.0',port=None):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'),override=False)
    if application is None:
        from app import app as application,engine
    config=uvicorn.Config(application,host=host,port=port or int(os.getenv('PORT','8000')),workers=1,
                          access_log=False,proxy_headers=True,timeout_graceful_shutdown=5)
    DotServer(config,engine).run()

if __name__=='__main__':run()
