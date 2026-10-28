"""Composited glass contrast on synthetic backgrounds; not a physical iPhone test."""
import asyncio,io,json,os
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785')
OUT=Path(os.getenv('TEST_OUTPUT_DIR','/workspace/scratch/ui77'))

def luminance(rgb):
 def linear(n):
  n=n/255
  return n/12.92 if n<=.04045 else ((n+.055)/1.055)**2.4
 return sum(x*y for x,y in zip((.2126,.7152,.0722),map(linear,rgb[:3])))
def contrast(a,b):
 x,y=sorted((luminance(a),luminance(b)),reverse=True)
 return (x+.05)/(y+.05)
async def main():
 OUT.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE);await page.locator('#password').fill('minimal-testing-password');await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden')
  await page.evaluate('''() => {
   const stage=document.createElement('div');stage.id='material-fixture';
   stage.style.cssText='position:fixed;inset:0;z-index:200;display:flex;flex-direction:column;gap:20px;align-items:center;justify-content:center';
   const bubble=document.createElement('div');bubble.className='user';bubble.style.cssText='width:calc(100% - 24px)';
   const message=document.createElement('div');message.className='message-bubble';message.textContent='رسالة اختبار';bubble.append(message);stage.append(bubble);
   const clone=document.getElementById('form').cloneNode(true);clone.removeAttribute('id');
   clone.querySelectorAll('[id]').forEach(e=>e.removeAttribute('id'));
   clone.style.cssText='width:calc(100% - 24px);margin:0';stage.append(clone);
   const panel=document.createElement('div');panel.className='tools glass';panel.style.cssText='position:static;width:calc(100% - 24px);max-width:none';
   const label=document.createElement('span');label.textContent='عناصر اختبار';label.style.cssText='padding:10px;color:var(--text)';panel.append(label);stage.append(panel);
   document.body.append(stage);
  }''')
  composer=page.locator('#material-fixture .composer');bounds=await composer.bounding_box()
  text_color=await composer.locator('textarea').evaluate("e=>getComputedStyle(e).color.match(/\\d+/g).map(Number)")
  placeholder_color=await composer.locator('textarea').evaluate("e=>getComputedStyle(e,'::placeholder').color.match(/\\d+/g).map(Number)")
  icon_color=await composer.locator('.icon-button').first.evaluate("e=>getComputedStyle(e).color.match(/\\d+/g).map(Number)")
  bubble=page.locator('#material-fixture .message-bubble');bubble_bounds=await bubble.bounding_box()
  panel=page.locator('#material-fixture .tools');panel_bounds=await panel.bounding_box()
  backgrounds={'black':'#000000','white':'#ffffff','color':'linear-gradient(115deg,#e89571,#377fc1,#f6d96b)',
   'moving-a':'repeating-linear-gradient(45deg,#fff 0 20px,#16111d 20px 40px)',
   'moving-b':'repeating-linear-gradient(45deg,#16111d 0 20px,#fff 20px 40px)'}
  results={}
  for name,value in backgrounds.items():
   await page.locator('#material-fixture').evaluate('(e,value)=>e.style.background=value',value)
   await page.wait_for_timeout(100)
   data=await page.screenshot()
   image=Image.open(io.BytesIO(data)).convert('RGB')
   # Sample the control material away from text, borders and buttons.
   bg=image.getpixel((int(bounds['x']+bounds['width']/2),int(bounds['y']+7)))
   text_ratio=contrast(text_color,bg);placeholder_ratio=contrast(placeholder_color,bg);icon_ratio=contrast(icon_color,bg)
   bubble_bg=image.getpixel((int(bubble_bounds['x']+bubble_bounds['width']-12),int(bubble_bounds['y']+7)))
   panel_bg=image.getpixel((int(panel_bounds['x']+panel_bounds['width']-12),int(panel_bounds['y']+7)))
   subtle_ratio=contrast(text_color,bubble_bg);strong_ratio=contrast(text_color,panel_bg)
   assert min(text_ratio,placeholder_ratio,subtle_ratio,strong_ratio)>=4.5 and icon_ratio>=3,(name,bg,text_ratio,placeholder_ratio,icon_ratio,subtle_ratio,strong_ratio)
   results[name]={'text':round(text_ratio,2),'placeholder':round(placeholder_ratio,2),'icon':round(icon_ratio,2),'subtle':round(subtle_ratio,2),'strong':round(strong_ratio,2)}
  await page.screenshot(path=str(OUT/'preview-materials-fixture.png'))
  await page.emulate_media(reduced_motion='reduce')
  assert await composer.evaluate("e=>getComputedStyle(e).transitionDuration") in ('0s','0s, 0s')
  session=await page.context.new_cdp_session(page)
  await session.send('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-transparency','value':'reduce'}]})
  reduced=await page.evaluate("matchMedia('(prefers-reduced-transparency: reduce)').matches")
  if reduced:
   assert await composer.evaluate("e=>getComputedStyle(e).backdropFilter")=='none'
   assert await composer.evaluate("e=>getComputedStyle(e).backgroundImage")=='none'
   assert await bubble.evaluate("e=>getComputedStyle(e).backgroundImage")=='none'
   assert await panel.evaluate("e=>getComputedStyle(e).backdropFilter")=='none'
  assert not errors,errors
  print(json.dumps({'contrast':results,'reduced_motion':True,'reduced_transparency_emulated':reduced,'fixture_only':True,'js_errors':errors}))
  await browser.close()
asyncio.run(main())
