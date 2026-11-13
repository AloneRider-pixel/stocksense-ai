import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { chromium } from 'playwright';

const server = createServer(async (req, res) => {
  try {
    const path = req.url === '/' ? 'index.html' : req.url.split('?')[0].slice(1);
    const data = await readFile(join('dist', path));
    res.setHeader('Content-Type', ({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[extname(path)] || 'application/octet-stream');
    res.end(data);
  } catch { res.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({headless:true, ...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH,args:['--no-sandbox']} : {})});
let passed = 0;
async function scenario(name, test) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem('stocksense_token','offline-fixture'));
  await page.clock.install();
  try { await test(page); passed++; console.log(`PASS ${name}`); }
  finally { await context.close(); }
}
try {
  await scenario('timeout preserves session, shows recovery, retry succeeds', async page => {
    let retry = false;
    await page.route('**/api/v1/**', async route => {
      if (!retry) return;
      await route.fulfill({json:{email:'fixture@example.invalid',full_name:'Fixture'},headers:{'access-control-allow-origin':'*'}});
    });
    await page.goto(base);
    await page.getByText('Loading StockSense AI…').waitFor();
    await page.clock.runFor(12010);
    await page.getByRole('heading',{name:'We could not restore your session yet'}).waitFor();
    assert.equal(await page.evaluate(()=>localStorage.getItem('stocksense_token')),'offline-fixture');
    if(process.env.EVIDENCE_DIR) await page.screenshot({path:`${process.env.EVIDENCE_DIR}/startup-timeout-desktop.png`});
    await page.setViewportSize({width:390,height:844});
    if(process.env.EVIDENCE_DIR) await page.screenshot({path:`${process.env.EVIDENCE_DIR}/startup-timeout-mobile.png`});
    retry = true;
    await page.getByRole('button',{name:'Retry connection'}).click();
    await page.getByRole('button',{name:'Sign out'}).waitFor();
  });
  await scenario('network failure preserves session; explicit sign-in clears it', async page => {
    await page.route('**/api/v1/**',route=>route.abort('failed'));
    await page.goto(base);
    await page.getByRole('button',{name:'Continue to sign in'}).waitFor();
    assert.equal(await page.evaluate(()=>localStorage.getItem('stocksense_token')),'offline-fixture');
    await page.getByRole('button',{name:'Continue to sign in'}).click();
    assert.equal(await page.evaluate(()=>localStorage.getItem('stocksense_token')),null);
    await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();
  });
  await scenario('401 clears invalid token and returns to landing', async page => {
    await page.route('**/api/v1/**',route=>route.fulfill({status:401,json:{error:{message:'Expired fixture'}},headers:{'access-control-allow-origin':'*'}}));
    await page.goto(base);
    await page.getByRole('button',{name:'Live dashboard'}).waitFor();
    assert.equal(await page.evaluate(()=>localStorage.getItem('stocksense_token')),null);
  });
  await scenario('server 500 does not discard a saved session', async page => {
    await page.route('**/api/v1/**',route=>route.fulfill({status:500,json:{error:{message:'Unavailable fixture'}},headers:{'access-control-allow-origin':'*'}}));
    await page.goto(base);
    await page.getByRole('button',{name:'Retry connection'}).waitFor();
    assert.equal(await page.evaluate(()=>localStorage.getItem('stocksense_token')),'offline-fixture');
  });
  console.log(`${passed} startup browser regressions passed; all API responses mocked.`);
} finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
