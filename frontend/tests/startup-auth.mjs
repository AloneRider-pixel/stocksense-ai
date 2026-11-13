import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { chromium } from 'playwright';

// Preload only build artifacts. Request paths never reach the filesystem.
const artifacts = new Map([['/', {data: await readFile('dist/index.html'), type: 'text/html'}]]);
for (const name of await readdir('dist/assets')) {
  const type = ({'.js':'application/javascript','.css':'text/css'})[extname(name)] || 'application/octet-stream';
  artifacts.set(`/assets/${name}`, {data: await readFile(join('dist/assets', name)), type});
}
const server = createServer((req, res) => {
  const artifact = artifacts.get(req.url.split('?')[0]);
  if (!artifact) { res.writeHead(404).end(); return; }
  res.setHeader('Content-Type', artifact.type);
  res.end(artifact.data);
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
  await scenario('historical versions and pooled-metric limits remain visible', async page => {
    await page.route('**/api/v1/**',async route=>{
      const p=new URL(route.request().url()).pathname;
      if(p.endsWith('/auth/me'))return route.fulfill({json:{email:'fixture@example.invalid',full_name:'Fixture'}});
      if(p.endsWith('/predictions'))return route.fulfill({json:[{id:1,symbol:'INFY',prediction_date:'2026-11-13',predicted_close:1141,model:'random-forest-v0.4:latest-bar-v1'}]});
      if(p.endsWith('/symbols'))return route.fulfill({json:[{symbol:'INFY',currency:'INR',exchange:'NSE'}]});
      if(p.includes('/history'))return route.fulfill({json:[]});
      return route.fulfill({json:{}});
    });
    await page.goto(base);await page.getByText('Prediction activity',{exact:true}).first().click();
    await page.getByText('random-forest-v0.4:latest-bar-v1',{exact:true}).waitFor();
    await page.getByText('₹1,141.00',{exact:true}).waitFor();
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/version-desktop.png`});
    await page.setViewportSize({width:390,height:844});
    await page.getByText('random-forest-v0.4:latest-bar-v1',{exact:true}).scrollIntoViewIfNeeded();
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/version-mobile.png`});
    await page.getByText('Model evaluation',{exact:true}).first().click();
    await page.getByText('Historical aggregate:',{exact:false}).waitFor();
  });
  console.log(`${passed} startup browser regressions passed; all API responses mocked.`);
} finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
