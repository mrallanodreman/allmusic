import { chromium } from 'playwright';

const base = 'http://127.0.0.1:8123';
const cases = [
  { path: '/allmusic', selector: '.stage', label: 'sin barra final' },
  { path: '/allmusic/', selector: '.stage', label: 'portada principal' },
  { path: '/allmusic/#playlists', selector: '#playlists', label: 'playlists antiguas' },
  { path: '/allmusic/#mymusic', selector: '#mymusic', label: 'panel de artista' },
  { path: '/allmusic/#cartelera', selector: '#cartelera', label: 'cartelera' },
  { path: '/allmusic/radio', selector: '.stage', label: 'alias radio' },
];

const browser = await chromium.launch({ headless: true });
const failures = [];
try {
  for (const entry of cases) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.url().includes('/assets/') && response.status() >= 400) {
        errors.push(`asset ${response.status()}: ${response.url()}`);
      }
    });
    try {
      const response = await page.goto(base + entry.path, { waitUntil: 'load', timeout: 20000 });
      await page.locator(entry.selector).waitFor({ state: 'visible', timeout: 15000 });
      await page.waitForTimeout(300);
      const fallback = await page.locator('#allmusic-boot').count();
      const boundary = await page.getByText('La cabina tuvo un problema al abrirse').count();
      const layout = await page.locator('.sidebar').count();
      if (fallback || boundary || !layout) {
        errors.push(`Fallback ${fallback}, error boundary ${boundary}, sidebar ${layout}`);
      }
      if (entry.path === '/allmusic/') {
        const like = page.locator('.stage__like-button');
        await like.waitFor({ state: 'visible', timeout: 10000 });
        const nextToMode = await like.evaluate((button) =>
          button.closest('.stage__controls') !== null &&
          button.previousElementSibling?.classList.contains('stage__mode-label')
        );
        if (!nextToMode) errors.push('El like debe quedar junto a MODO en los controles del reproductor');
        if (await like.getAttribute('aria-pressed') !== 'false') {
          errors.push('El like del reproductor debe iniciar apagado');
        }
        await like.click();
        await page.waitForFunction(() =>
          document.querySelector('.stage__like-button')?.textContent.includes('5')
        );
        if (await like.getAttribute('aria-pressed') !== 'true') {
          errors.push('El like no se activó en la canción sonando');
        }
      }
      if (response.status() !== 200) errors.push(`HTTP status ${response.status()}`);
      if (entry.path === '/allmusic' && !page.url().includes('/allmusic/')) {
        errors.push('No redirect to canonical /allmusic/');
      }
      if (errors.length) throw new Error(errors.join(' | '));
      console.log(`PASS ${entry.label}: ${page.url()}`);
    } catch (error) {
      failures.push({ label: entry.label, error: error.message, jsErrors: errors });
      console.error(`FAIL ${entry.label}: ${error.message}`);
    } finally {
      await page.close();
    }
  }
} finally {
  await browser.close();
}
if (failures.length) {
  console.error('AllMusic browser smoke failures:', JSON.stringify(failures, null, 2));
  process.exit(1);
}
