import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, readdir, mkdir } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { chromium } from 'playwright';

const artifacts = new Map([['/', {data: await readFile('dist/index.html'), type:'text/html'}]]);
for (const name of await readdir('dist/assets')) artifacts.set(`/assets/${name}`, {
  data: await readFile(join('dist/assets',name)),
  type: ({'.js':'application/javascript','.css':'text/css'})[extname(name)] || 'application/octet-stream'
});
const server = createServer((req,res) => {
  const file=artifacts.get(req.url.split('?')[0]);
  if(!file) {res.writeHead(404).end();return;}
  res.setHeader('Content-Type',file.type);res.end(file.data);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',args:['--no-sandbox']});
const evidence=process.env.EVIDENCE_DIR || '/tmp/ss-data-health-pixels';
await mkdir(evidence,{recursive:true});
const sample={checked_at:'2026-11-18T16:00:00+00:00',stored_sources:[{
  provider:'fixture_csv (synthetic local UI test)',stored_rows:120,symbols:2,
  latest_session:'2026-11-10',last_ingested_at:'2026-11-18T12:00:00',public_display:'not_cleared',
  freshness:'unverified_calendar_not_integrated',warning:'Synthetic UI fixture. Storage counts are not proof of current prices.'
}],limitations:['No approved session calendar is integrated here.','Public-display rights have not been cleared by this check.','SEBI RSS is regulatory headlines only; company filings and market news are not connected.'],source_policies:[
  {id:'sebi_rss',collection:'official_feed',public_display:'review_required'},
  {id:'bse',collection:'written_consent_required',public_display:'permission_required'}
]};
let mode='normal',calls=0;
try {
  const context=await browser.newContext();const page=await context.newPage();
  await page.addInitScript(()=>localStorage.setItem('stocksense_token','offline-ui-fixture'));
  await page.route('**/api/v1/**',async route=>{
    const url=new URL(route.request().url());let json=[];
    if(url.pathname.endsWith('/auth/me')) json={email:'fixture@example.invalid',full_name:'Local fixture'};
    if(url.pathname.endsWith('/data-health')) {
      calls++;
      if(mode==='error') return route.fulfill({headers:{'access-control-allow-origin':'*'},status:503,json:{error:{message:'Fixture service unavailable'}}});
      json=mode==='empty'?{...sample,stored_sources:[]}:sample;
    }
    if(url.pathname.endsWith('/watchlist')) json={symbols:[]};
    if(url.pathname.endsWith('/public/market-overview')) json={symbols:[]};
    return route.fulfill({headers:{'access-control-allow-origin':'*'},json});
  });
  for(const width of [320,390,1280]) {
    await page.setViewportSize({width,height:900});await page.goto(base);
    await page.getByRole('button',{name:'Data health',exact:true}).focus();await page.keyboard.press('Enter');
    await page.getByRole('heading',{name:'Data health and sources'}).waitFor();
    await page.getByText('fixture_csv (synthetic local UI test)',{exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow ${width}`);
    await page.screenshot({path:`${evidence}/data-health-${width}.png`,fullPage:true});
  }
  mode='error';await page.reload();await page.getByRole('button',{name:'Data health',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Fixture service unavailable'}).waitFor();
  mode='empty';await page.getByRole('button',{name:'Retry data check'}).click();
  await page.getByText('No market bars are stored. This is missing data, not a zero price.').waitFor();
  await page.setViewportSize({width:390,height:900});await page.screenshot({path:`${evidence}/data-health-empty-390.png`,fullPage:true});
  console.log(`PASS data-health: 3 widths, keyboard navigation, no overflow, API error/retry, empty state; ${calls} health reads; no provider fetches.`);
  await context.close();
} finally {await browser.close();await new Promise(r=>server.close(r));}
