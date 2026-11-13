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
  await scenario('late previous-symbol responses cannot overwrite selected market data', async page => {
    let lateAapl;
    const bar=(symbol,close)=>({symbol,date:'2026-11-13',open:close,high:close+1,low:close-1,close,volume:100,source_provider:'fixture'});
    await page.route('**/api/v1/**', async route => {
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/auth/me'))return route.fulfill({json:{email:'fixture@example.invalid',full_name:'Fixture'}});
      if(path.endsWith('/public/market-overview'))return route.fulfill({json:{symbols:[{symbol:'GOLD',name:'Gold',currency:'USD'}]}});
      if(path.includes('/stocks/AAPL/history')){lateAapl=route;return;}
      if(path.includes('/stocks/GOLD/history'))return route.fulfill({json:[bar('GOLD',5000)]});
      if(path.includes('/indicators'))return route.fulfill({json:{}});
      if(path.endsWith('/symbols'))return route.fulfill({json:[]});
      if(path.endsWith('/predictions'))return route.fulfill({json:[]});
      return route.fulfill({json:{}});
    });
    await page.goto(base);
    await page.getByText('Latest close · GOLD').waitFor();
    await page.getByText('$5,000.00',{exact:true}).waitFor();
    assert.ok(lateAapl,'initial AAPL request captured');
    await lateAapl.fulfill({json:[bar('AAPL',300)]});
    await page.waitForTimeout(100);
    assert.ok(await page.getByText('$5,000.00',{exact:true}).isVisible(),'late AAPL must not replace GOLD');
    assert.equal(await page.getByText('$300.00',{exact:true}).count(),0);
  });
  await scenario('wrong-symbol history is shown as an error and cannot produce a prediction', async page => {
    let writes=0;
    await page.route('**/api/v1/**', async route => {
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/auth/me'))return route.fulfill({json:{email:'fixture@example.invalid',full_name:'Fixture'}});
      if(path.endsWith('/public/market-overview'))return route.fulfill({json:{symbols:[{symbol:'GOLD',name:'Gold',currency:'USD'}]}});
      if(path.includes('/history'))return route.fulfill({json:Array.from({length:12},(_,i)=>({symbol:'AAPL',date:'2026-11-13',close:300,volume:100}))});
      if(path.endsWith('/predict')){writes++;return route.fulfill({json:{}});}
      if(path.endsWith('/predictions')||path.endsWith('/symbols'))return route.fulfill({json:[]});
      return route.fulfill({json:{}});
    });
    await page.goto(base);
    await page.getByText('Could not load GOLD price history: The server returned data for a different symbol.').waitFor();
    await page.getByRole('button',{name:'Run prediction'}).click();
    await page.getByText('Prediction stopped: market history does not match the selected symbol.').waitFor();
    assert.equal(writes,0,'mismatched data must never be submitted as a forecast');
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/wrong-symbol-error-desktop.png`});
    await page.setViewportSize({width:390,height:844});
    await page.getByText('Prediction stopped: market history does not match the selected symbol.').scrollIntoViewIfNeeded();
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/wrong-symbol-error-mobile.png`});
  });
  await scenario('dashboard separates stored/scored records and charts one symbol in its own currency', async page => {
    const row=(id,symbol,day,actual)=>({id,symbol,prediction_date:day,predicted_close:1100+id,actual_close:actual,baseline_close:1090,percentage_error:0.1,model:'historical-v0.4'});
    const records=[row(4,'INFY','2026-11-13',null),row(3,'INFY','2026-11-12',1105),row(2,'INFY','2026-11-11',1102),row(1,'RELIANCE','2026-11-11',1200)];
    await page.route('**/api/v1/**',async route=>{
      const u=new URL(route.request().url()),p=u.pathname;
      if(p.endsWith('/auth/me'))return route.fulfill({json:{email:'fixture@example.invalid',full_name:'Fixture'}});
      if(p.endsWith('/predictions')){assert.equal(u.searchParams.get('limit'),'100');return route.fulfill({json:records});}
      if(p.endsWith('/predictions/evaluation'))return route.fulfill({json:{evaluated_predictions:3,directional_accuracy_pct:100,mae:98765,baseline_mae:87654,improvement_vs_persistence_pct:87.65,mape_pct:0.25}});
      if(p.endsWith('/metrics'))return route.fulfill({json:{model_version:'sample-v0.4',trained_at:'2026-11-13T18:27:58Z',data_source:'csv:sample.csv',data_sha256:'a'.repeat(64),source_rows:180,test_rows:140,folds:5,mae:0.165}});
      if(p.endsWith('/symbols'))return route.fulfill({json:[{symbol:'INFY',currency:'INR'},{symbol:'RELIANCE',currency:'INR'}]});
      if(p.includes('/history'))return route.fulfill({json:[]});
      return route.fulfill({json:{}});
    });
    await page.goto(base);
    const stored=page.locator('article').filter({has:page.getByText('Stored records shown',{exact:true})});
    await stored.getByText('4',{exact:true}).waitFor();
    await page.getByText('3 scored records; pooled versions',{exact:true}).waitFor();
    assert.equal(await page.getByText('Every prediction gets graded.',{exact:true}).count(),0);
    await page.getByText('Model evaluation',{exact:true}).first().click();
    await page.getByRole('img',{name:'Predicted vs actual closes for INFY',exact:true}).waitFor();
    await page.getByText('INFY · INR · 2 scored records shown',{exact:true}).waitFor();
    assert.equal(await page.locator('svg[aria-label="Predicted vs actual closes for INFY"]').textContent().then(t=>t.includes('$')),false);
    assert.equal(await page.locator('svg[aria-label="Predicted vs actual closes for INFY"]').textContent().then(t=>t.includes('₹')),true);
    await page.getByText('Model label: sample-v0.4.',{exact:false}).waitFor();
    await page.getByText('Per symbol only',{exact:true}).waitFor();
    await page.getByText('0.25%',{exact:true}).waitFor();
    assert.equal((await page.locator('body').textContent()).includes('98765'),false);
    assert.equal((await page.locator('body').textContent()).includes('87654'),false);
    assert.equal((await page.locator('body').textContent()).includes('+87.65%'),false);
    await page.getByText('This identifies the evaluation data, not the deployed model', {exact:false}).waitFor();
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/dashboard-records-desktop.png`,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.getByLabel('Chart symbol').scrollIntoViewIfNeeded();
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/dashboard-records-mobile.png`});
    await page.getByLabel('Chart symbol').selectOption('RELIANCE');
    await page.getByText('At least two scored records for the same symbol are needed',{exact:false}).waitFor();
    assert.equal(await page.getByRole('img',{name:'Predicted vs actual closes for INFY',exact:true}).count(),0);
  });
  await scenario('manual sign-in recovery preserves fields and never retries on its own', async page => {
    await page.addInitScript(()=>localStorage.removeItem('stocksense_token'));
    let loginCalls=0,releaseFirst;
    await page.route('**/api/v1/**',async route=>{
      const p=new URL(route.request().url()).pathname;
      if(p.endsWith('/auth/login')){
        loginCalls++;
        if(loginCalls===1){releaseFirst=()=>route.fulfill({status:503,json:{error:{message:'Fixture server not ready. Please retry manually.'}}});return;}
        return route.fulfill({json:{access_token:'recovered-fixture-token'}});
      }
      if(p.endsWith('/auth/me'))return route.fulfill({json:{email:'fixture@example.invalid',full_name:'Fixture'}});
      if(p.endsWith('/predictions')||p.endsWith('/symbols')||p.includes('/history'))return route.fulfill({json:[]});
      return route.fulfill({json:{}});
    });
    await page.goto(base);await page.getByRole('button',{name:'Sign in',exact:true}).first().click();
    await page.getByLabel('Email',{exact:true}).fill('fixture@example.invalid');
    await page.getByLabel('Password',{exact:true}).fill('fixture-only-not-a-real-secret');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('status').filter({hasText:'cold start can take several minutes'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Working...',exact:true}).isDisabled(),true);
    await page.clock.runFor(300000);assert.equal(loginCalls,1);
    await page.getByRole('alert').filter({hasText:'We could not finish signing you in'}).waitFor();
    await releaseFirst().catch(()=>{});
    assert.equal(await page.getByLabel('Email',{exact:true}).inputValue(),'fixture@example.invalid');
    assert.equal(await page.getByLabel('Password',{exact:true}).inputValue(),'fixture-only-not-a-real-secret');
    assert.equal(await page.getByRole('button',{name:'Sign in',exact:true}).isEnabled(),true);
    await page.getByLabel('Password',{exact:true}).fill('');
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/auth-recovery-desktop.png`});
    await page.setViewportSize({width:390,height:844});
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/auth-recovery-mobile.png`});
    await page.getByLabel('Password',{exact:true}).fill('fixture-only-not-a-real-secret');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('button',{name:'Sign out',exact:true}).waitFor();
    assert.equal(loginCalls,2);
  });
  await scenario('landing distinguishes market history from supported forecasts and pooled results', async page => {
    await page.route('**/api/v1/**', async route => {
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/auth/me'))return route.fulfill({status:401,json:{error:{message:'Expired fixture'}}});
      if(path.endsWith('/public/accuracy'))return route.fulfill({json:{overall:{evaluated_predictions:2,directional_accuracy_pct:50,mae:1.2},symbols:[]}});
      if(path.endsWith('/public/predictions/latest'))return route.fulfill({json:{predictions:[{symbol:'INFY',prediction_date:'2026-11-12',predicted_close:1450,direction:'up'}]}});
      return route.fulfill({json:{symbols:[]}});
    });
    await page.goto(base);
    await page.getByRole('heading',{name:'Market history and supported NSE-equity forecasts.'}).waitFor({timeout:3000});
    assert.equal(await page.getByText('Next-trading-day forecasts for NSE, metals and INR pairs,',{exact:false}).count(),0);
    await page.getByText('zero-volume gold, silver and FX predictions are not supported.',{exact:false}).waitFor();
    await page.getByText('pooled all-symbol statistics.',{exact:false}).waitFor();
    await page.getByText('Pending forecasts, cached responses and failed saves are not new scored records.',{exact:false}).waitFor();
    await page.getByText('Latest stored forecasts · may include pending and scored records',{exact:true}).waitFor();
    assert.equal(await page.getByText('Latest stored forecasts · pending until matching realized closes are available',{exact:true}).count(),0);
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/landing-supported-desktop.png`});
    await page.setViewportSize({width:390,height:844});
    if(process.env.EVIDENCE_DIR)await page.screenshot({path:`${process.env.EVIDENCE_DIR}/landing-supported-mobile.png`,fullPage:true});
  });
  console.log(`${passed} startup browser regressions passed; all API responses mocked.`);
} finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
