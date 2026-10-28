"""Real settings/API interaction; usage rendering sample is explicitly synthetic."""
import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785')
OUT=Path(os.getenv('TEST_OUTPUT_DIR','.'))
async def main():
 OUT.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
  await page.goto(BASE);await page.locator('#password').fill(os.getenv('TEST_APP_PASSWORD','minimal-testing-password'));await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden')
  await page.locator('#settingsOpen').click();await page.wait_for_function('()=>modelProfiles!==null')
  await page.locator('#modelProvider').select_option('openrouter');await page.locator('#modelName').fill('usage-fixture');await page.locator('#modelKey').fill('ui-fixture-only')
  await page.locator('#modelForm details summary').click()
  for key,value in [('modelContext','65536'),('priceInput','2'),('priceOutput','4'),('priceCached','1'),('priceSource','UI TEST FIXTURE')]:await page.locator('#'+key).fill(value)
  await page.locator('#saveModel').click();await page.wait_for_function('()=>modelResult.textContent.includes("تم الحفظ")')
  assert await page.locator('#modelKey').input_value()==''
  await page.locator('#modelForm details summary').click()
  await page.locator('details').filter(has=page.locator('#limitsForm')).locator('summary').click()
  await page.locator('#tokenLimit').fill('500');await page.locator('#costLimit').fill('0.005');await page.locator('#saveLimits').click();await page.wait_for_function('()=>limitsResult.textContent.includes("تم الحفظ")')
  profile=await page.evaluate("async()=>await(await fetch('/api/model/settings')).json()")
  assert profile['profiles']['openrouter']['pricing']['input']==2
  assert profile['profiles']['openrouter']['context_window']==65536
  await page.locator('#modelName').fill('another-model')
  assert await page.locator('#priceInput').input_value()==''
  assert await page.locator('#modelContext').input_value()=='32768'
  await page.evaluate('showModelProfile()')
  await page.locator('#limitsForm').scroll_into_view_if_needed();await page.screenshot(path=str(OUT/'preview-usage-settings.png'))
  assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
  await page.locator('#tokenLimit').fill('');await page.locator('#costLimit').fill('');await page.locator('#saveLimits').click();await page.wait_for_timeout(300)
  await page.locator('#deleteModel').click();await page.wait_for_function('()=>modelResult.textContent.includes("تم حذف")');await page.locator('#settingsClose').click()
  sample={'calls':2,'total_tokens':1200,'cached_tokens':400,'unknown_calls':1,'estimated_cost_usd':None,'priced_calls':1,'known_cost_usd':.0024}
  await page.evaluate('(u)=>renderUsage(u)',sample)
  assert 'غير متاحة' in await page.locator('#usageSummary').text_content()
  sample['recent']=[{'elapsed_ms':1250}]
  await page.evaluate('(u)=>renderUsage(u)',sample)
  assert 'آخر طلب' in await page.locator('#usageSummary').text_content()
  assert not errors,errors
  print(json.dumps({'model_pricing_and_context_persisted':True,'optional_limits_saved_and_cleared':True,'missing_usage_not_zero':True,'mobile_overflow':False,'js_errors':errors}))
  await b.close()
asyncio.run(main())
