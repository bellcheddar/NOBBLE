import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
await p.waitForTimeout(4000);
const info = await p.evaluate(() => {
  const host = document.getElementById('viewer-canvas');
  const cv = host ? host.querySelector('canvas') : null;
  let nonBlank = null;
  if (cv) {
    try {
      const probe = document.createElement('canvas');
      probe.width = cv.width; probe.height = cv.height;
      probe.getContext('2d').drawImage(cv, 0, 0);
      const d = probe.getContext('2d').getImageData(0, 0, probe.width, probe.height).data;
      const seen = new Set();
      for (let i = 0; i < d.length; i += 4000) { seen.add(d[i] + ',' + d[i+1] + ',' + d[i+2]); }
      nonBlank = seen.size;
    } catch (e) { nonBlank = 'readback blocked: ' + e.message; }
  }
  return {
    molstarCanvasFound: !!cv,
    drawingBuffer: cv ? [cv.width, cv.height] : null,
    cssSize: cv ? [cv.clientWidth, cv.clientHeight] : null,
    distinctColours: nonBlank,
    readout: (document.getElementById('viewer-readout') || {}).textContent,
    emptyHidden: (document.getElementById('viewer-empty') || {}).hidden,
    controls: [...document.querySelectorAll('[data-view]')].map(b => b.dataset.view)
  };
});
console.log(JSON.stringify(info, null, 1));
await b.close();
