"""Run with the SAME Python environment used to start the application."""
import asyncio,json,sys
async def main():
    try:
        from runtime_checks import browser_runtime
        status,path=await browser_runtime()
        print(json.dumps({'python':sys.executable,'browser':status,'expected_browser':path},ensure_ascii=False,indent=2))
    except ImportError:
        print('Run: python -m pip install -r requirements.txt');return 1
    return 0 if status['installed'] else 1
if __name__=='__main__':sys.exit(asyncio.run(main()))
