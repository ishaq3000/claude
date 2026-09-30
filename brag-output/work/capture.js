// Render index.html frame by frame.
//   node capture.js stills <t1> <t2> ...   -> stills/<t>.jpg
//   node capture.js video [workers]        -> chunks/*.mp4, then video.mp4
// Frame 0 is replaced by the poster frame (POSTER_T) so thumbnails show it.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const { chromium } = require('playwright-core');

const ROOT = __dirname;
const FPS = 30;
const FFMPEG = execFileSync('python3', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim();
const EXE = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'timeline.json'), 'utf8'));
const POSTER_T = Number(process.env.POSTER_T || (TL.scenes[0].start + TL.scenes[0].dur - 1.5));
const MIME = { '.html': 'text/html', '.ttf': 'font/ttf', '.js': 'text/javascript', '.json': 'application/json' };

function serve() {
  return new Promise(res => {
    const srv = http.createServer((q, r) => {
      const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
      if (!f.startsWith(ROOT) || !fs.existsSync(f)) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' });
      fs.createReadStream(f).pipe(r);
    }).listen(0, () => res(srv));
  });
}

async function openPage(browser, port) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await page.addInitScript(tl => { window.TIMELINE = tl; }, TL);
  await page.goto(`http://127.0.0.1:${port}/index.html`);
  await page.evaluate(() => document.fonts.ready);
  return page;
}

async function stills(times) {
  const srv = await serve();
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await openPage(browser, srv.address().port);
  fs.mkdirSync(path.join(ROOT, 'stills'), { recursive: true });
  for (const t of times) {
    await page.evaluate(([t, p]) => renderAt(t, p), [t, t === POSTER_T]);
    await page.screenshot({ path: path.join(ROOT, 'stills', `${String(t).padStart(6, '0')}.jpg`), type: 'jpeg', quality: 85 });
  }
  await browser.close(); srv.close();
}

async function video(workers) {
  const total = Math.ceil(TL.total * FPS);
  const srv = await serve();
  const dir = path.join(ROOT, 'chunks');
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
  const per = Math.ceil(total / workers);
  const t0 = Date.now();
  let done = 0;
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const a = w * per, b = Math.min(total, a + per);
    const browser = await chromium.launch({ executablePath: EXE });
    const page = await openPage(browser, srv.address().port);
    const ff = spawn(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(FPS), path.join(dir, `c${String(w).padStart(2, '0')}.mp4`)],
      { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let f = a; f < b; f++) {
      await page.evaluate(([t, p]) => renderAt(t, p), [f === 0 ? POSTER_T : f / FPS, f === 0]);
      const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (++done % 300 === 0) {
        const s = (Date.now() - t0) / 1000;
        console.log(`${done}/${total} frames  ${(done / s).toFixed(1)} fps  eta ${((total - done) / (done / s) / 60).toFixed(1)} min`);
      }
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    await browser.close();
  }));
  srv.close();
  const list = fs.readdirSync(dir).filter(f => f.endsWith('.mp4')).sort().map(f => `file '${path.join(dir, f)}'`).join('\n');
  fs.writeFileSync(path.join(dir, 'list.txt'), list);
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'), '-c', 'copy', path.join(ROOT, 'video.mp4')]);
  console.log(`video.mp4: ${total} frames in ${((Date.now() - t0) / 60000).toFixed(1)} min`);
}

const [mode, ...rest] = process.argv.slice(2);
(mode === 'stills' ? stills(rest.map(Number)) : video(Number(rest[0] || 4))).catch(e => { console.error(e); process.exit(1); });
