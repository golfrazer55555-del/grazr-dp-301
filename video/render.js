// Renders index.html frame-by-frame with Playwright and muxes with ffmpeg.
// usage: node render.js [out.mp4] [--times=3.5,8,...]  (--times writes PNG stills instead)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const FPS = 30, DUR = 30;
const dir = __dirname;
const args = process.argv.slice(2);
const timesArg = args.find(a => a.startsWith('--times='));
const out = args.find(a => !a.startsWith('--')) || path.join(dir, 'out', 'GRAZR_DP-301_promo.mp4');

(async () => {
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(dir, 'index.html'));
  await page.evaluate(() => window.ready);
  const shot = async t => { await page.evaluate(t => window.render(t), t); return page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: 1920, height: 1080 } }); };

  if (timesArg) {
    const fs = require('fs');
    for (const t of timesArg.slice(8).split(',').map(Number)) fs.writeFileSync(path.join(path.dirname(out), `still_${t.toFixed(2)}.png`), await shot(t));
    await browser.close(); return;
  }
  require('fs').mkdirSync(path.dirname(out), { recursive: true });
  const A = path.join(dir, 'audio');
  const ff = spawn('ffmpeg', ['-y', '-v', 'error',
    '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-ss', '5.515', '-t', String(DUR), '-i', path.join(A, 'Cutscene Crush - Blue Deer Studio.mp3'),
    '-ss', '1.2', '-i', path.join(dir, '..', 'Putter-sound.m4a'),
    '-ss', '1.2', '-i', path.join(dir, '..', 'Putter-sound.m4a'),
    '-filter_complex',
    // music: fade in/out; impact #1 lands at 15.00s (music break), #2 on the logo at 27.05s
    '[1:a]volume=0.62,volume=\'if(between(t,26.9,27.6),0.55,1)\':eval=frame,afade=t=in:st=0:d=0.4,afade=t=out:st=27.6:d=2.4[m];' +
    '[2:a]volume=1.0,adelay=14897|14897[h1];' +
    '[3:a]volume=0.9,adelay=26947|26947[h2];' +
    '[m][h1][h2]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.89[a]',
    '-map', '0:v', '-map', '[a]',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    '-c:a', 'aac', '-b:a', '256k', '-t', String(DUR), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const N = FPS * DUR;
  for (let i = 0; i < N; i++) {
    const buf = await shot(i / FPS);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 90 === 0) process.stdout.write(`frame ${i}/${N}\n`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.log('done:', out);
})();
