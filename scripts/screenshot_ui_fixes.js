const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const UI_URL = process.env.UI_URL || 'http://localhost:8080';
const OUTPUT_DIR = path.join(__dirname, '..', 'UI fixes', '2026-03-20');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

const pages = [
  { path: '/command', name: 'CommandCenter' },
  { path: '/signals', name: 'LiveSignalFeed' },
  { path: '/intelligence', name: 'IntelligenceCenter' },
  { path: '/ai-referee', name: 'AiReferee' },
  { path: '/performance', name: 'Performance' },
  { path: '/experiments', name: 'Experiments' },
  { path: '/portfolio', name: 'Portfolio' },
  { path: '/shadow-trades', name: 'ShadowTrades' },
  { path: '/system-health', name: 'SystemHealth' },
  { path: '/strategy-lab', name: 'StrategyLab' },
  { path: '/history', name: 'History' },
  { path: '/settings', name: 'Settings' },
  { path: '/orders', name: 'Orders' },
  { path: '/activities', name: 'Activities' },
  { path: '/calendar', name: 'Calendar' },
  { path: '/assets', name: 'Assets' },
];

async function takeScreenshots() {
  console.log(`🚀 Starting screenshot capture for UI fixes...`);
  console.log(`📁 Output directory: ${OUTPUT_DIR}`);
  console.log(`🌐 UI URL: ${UI_URL}\n`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  for (const { path: pagePath, name } of pages) {
    try {
      const url = `${UI_URL}${pagePath}`;
      console.log(`📸 Capturing ${name} (${pagePath})...`);
      
      await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
      
      // Wait for content to load
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Scroll to bottom to trigger lazy loading
      await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Scroll back to top
      await page.evaluate(() => {
        window.scrollTo(0, 0);
      });
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const screenshotPath = path.join(OUTPUT_DIR, `${name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`   ✅ Saved: ${screenshotPath}`);
    } catch (error) {
      console.error(`   ❌ Error capturing ${name}: ${error.message}`);
    }
  }

  await browser.close();
  console.log(`\n✨ Screenshot capture complete!`);
  console.log(`📁 Screenshots saved to: ${OUTPUT_DIR}`);
}

takeScreenshots().catch(console.error);
