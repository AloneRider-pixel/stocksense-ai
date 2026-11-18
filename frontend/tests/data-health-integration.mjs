// Real local auth + data-health API + SQLite + built UI. Other dashboard routes
// are blocked fixtures to avoid any market-provider request during this test.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, readdir, mkdtemp, rm, mkdir } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { chromium } from 'playwright';
const dir=await mkdtemp(join(tmpdir(),'ss-health-integration-'));
const tokenPath=join(dir,'token');
const backend=spawn(process.env.PYTHON || 'python',['-m','scripts.data_health_browser_fixture'],{
  cwd:'..',env:{...process.env,DATABASE_URL:`sqlite+pysqlite:///${dir}/fixture.db`,DEMO_MODE:'false',ENVIRONMENT:'development',MARKET_DATA_PROVIDER:'csv',CORS_ORIGINS:'*',FIXTURE_TOKEN_PATH:tokenPath},stdio:['ignore','pipe','pipe']
});
let backendLog='';backend.stdout.on('data',d=>backendLog+=d);backend.stderr.on('data',d=>backendLog+=d);
const artifacts=new Map([['/',{data:await readFile('dist/index.html'),type:'text/html'}]]);
for(const name of await readdir('dist/assets'))artifacts.set(`/assets/${name}`,{data:await readFile(join('dist/assets',name)),type:({'.js':'application/javascript','.css':'text/css'})[extname(name)]||'application/octet-stream'});
const server=createServer((req,res)=>{const f=artifacts.get(req.url.split('?')[0]);if(!f)return res.writeHead(404).end();res.setHeader('Content-Type',f.type);res.end(f.data)});
let browser;
try {
  let up=false;
  for(let i=0;i<100;i++){
    if(backend.exitCode!==null)throw new Error(backendLog);
    try {up=(await fetch('http://127.0.0.1:8000/health/live')).ok;if(up)break;}catch{}
    await new Promise(r=>setTimeout(r,100));
  }
  assert.ok(up,'local backend started');
  const token=await readFile(tokenPath,'utf8');
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:900}});
  await page.addInitScript(token=>localStorage.setItem('stocksense_token',token),token);
  let realReads=0;
  await page.route('**/api/v1/**',route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/auth/me')||path.endsWith('/data-health')){realReads++;return route.continue();}
    return route.fulfill({json:path.endsWith('/public/market-overview')?{symbols:[]}:[],headers:{'access-control-allow-origin':'*'}});
  });
  page.on('pageerror',e=>console.error(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.getByRole('button',{name:'Data health',exact:true}).click({timeout:5000}).catch(async e=>{console.error(await page.locator('body').innerText());console.error(backendLog);throw e;});
  await page.getByText('synthetic-local-integration',{exact:true}).waitFor();
  await page.getByText('2026-11-10',{exact:true}).waitFor();
  await page.getByText('No approved session calendar is integrated here; do not infer freshness from collection time.',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  const evidence=process.env.EVIDENCE_DIR||dir;await mkdir(evidence,{recursive:true});
  await page.screenshot({path:join(evidence,'data-health-api-integrated-390.png'),fullPage:true});
  assert.ok(realReads>=2);
  console.log('PASS real local auth + SQLite aggregate API + built data-health UI; synthetic records, no provider calls.');
} finally {
  if(browser)await browser.close();
  if(server.listening)await new Promise(r=>server.close(r));
  const stopped=new Promise(r=>backend.once('exit',r));backend.kill('SIGTERM');if(backend.exitCode===null)await stopped;
  await rm(dir,{recursive:true,force:true});
}
