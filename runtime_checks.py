"""Local dependency checks; no model requests or browser launch."""
import os
from pathlib import Path
from playwright.async_api import async_playwright
class RuntimeDependencyError(RuntimeError):
    def __init__(self,code,message):super().__init__(message);self.code=code
async def browser_runtime():
    try:
        async with async_playwright() as p:
            executable=os.getenv('CHROMIUM_PATH') or p.chromium.executable_path
    except FileNotFoundError:
        return {'installed':False,'code':'PLAYWRIGHT_DRIVER_MISSING','message':'برنامج Playwright الداخلي غير موجود. أعد تثبيت المتطلبات داخل نفس بيئة Python بالأمر python -m pip install --force-reinstall playwright ثم python -m playwright install chromium.'},''
    available=Path(executable).is_file() and os.access(executable,os.X_OK)
    return {'installed':available,'code':'ready' if available else 'BROWSER_MISSING','message':'المتصفح جاهز' if available else 'Chromium غير موجود أو مساره غير صحيح. أعد النشر باستخدام Dockerfile المرفق، أو ثبّت المتصفح بالأمر python -m playwright install chromium.'},executable
async def require_browser():
    status,path=await browser_runtime()
    if not status['installed']:raise RuntimeDependencyError(status['code'],status['message'])
    return path
