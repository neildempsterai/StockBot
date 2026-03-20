#!/usr/bin/env node
/**
 * Screenshot all StockBot pages for review
 * Usage: node scripts/screenshot_all_pages.js
 */

const fs = require('fs');
const path = require('path');

// Pages to screenshot (from router.tsx)
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

const baseUrl = process.env.UI_URL || 'http://localhost:8080';
const outputDir = path.join(__dirname, '..', 'screens', '2026-03-20');

// Create output directory
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

console.log(`📸 Screenshot script for StockBot UI review`);
console.log(`Base URL: ${baseUrl}`);
console.log(`Output directory: ${outputDir}`);
console.log(`Pages to capture: ${pages.length}\n`);

// Check if puppeteer is available
let puppeteer;
try {
  puppeteer = require('puppeteer');
} catch (e) {
  console.error('❌ Puppeteer not found. Installing...');
  console.log('Run: npm install puppeteer --save-dev');
  console.log('Or use: npx puppeteer scripts/screenshot_all_pages.js');
  process.exit(1);
}

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  for (const { path: pagePath, name } of pages) {
    try {
      console.log(`📷 Capturing ${name} (${pagePath})...`);
      const url = `${baseUrl}${pagePath}`;
      await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
      
      // Wait a bit for any animations/loading to complete
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Scroll to bottom to load lazy content
      await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Scroll back to top
      await page.evaluate(() => {
        window.scrollTo(0, 0);
      });
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const screenshotPath = path.join(outputDir, `${name}.png`);
      await page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });
      
      console.log(`   ✅ Saved: ${screenshotPath}`);
    } catch (error) {
      console.error(`   ❌ Error capturing ${name}: ${error.message}`);
    }
  }

  await browser.close();
  console.log(`\n✅ Screenshot capture complete!`);
  console.log(`📁 All screenshots saved to: ${outputDir}`);
})();
