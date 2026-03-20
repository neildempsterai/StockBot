#!/usr/bin/env node
/**
 * Screenshot all StockBot pages for Updated UI review
 * Usage: node scripts/screenshot_updated_ui.js
 */

const fs = require('fs');
const path = require('path');

// Get current date and time
const now = new Date();
const dateStr = now.toISOString().split('T')[0]; // YYYY-MM-DD
const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '-'); // HH-MM-SS
const folderName = `Updated UI ${dateStr} ${timeStr}`;

// Pages to screenshot (from router.tsx)
const pages = [
  { path: '/command', name: 'CommandCenter' },
  { path: '/signals', name: 'LiveSignalFeed' },
  { path: '/intelligence', name: 'PremarketPrep' },
  { path: '/ai-referee', name: 'AIAssessments' },
  { path: '/performance', name: 'Outcomes' },
  { path: '/experiments', name: 'ModeAnalysis' },
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
const outputDir = path.join(__dirname, '..', 'screens', folderName);

// Create output directory
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

console.log(`📸 Screenshot script for Updated UI - ${folderName}`);
console.log(`Base URL: ${baseUrl}`);
console.log(`Output directory: ${outputDir}\n`);

// Check if puppeteer is available
let puppeteer;
try {
  puppeteer = require('puppeteer');
} catch (e) {
  console.error('❌ Puppeteer not found. Installing...');
  console.log('Run: npm install puppeteer --save-dev');
  console.log('Or use: npx puppeteer scripts/screenshot_updated_ui.js');
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
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Scroll to bottom to load lazy content
      await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Scroll back to top
      await page.evaluate(() => {
        window.scrollTo(0, 0);
      });
      await new Promise(resolve => setTimeout(resolve, 1000));
      
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
  
  // Create README
  const readmePath = path.join(outputDir, 'README.md');
  const readmeContent = `# Updated UI Screenshots - ${folderName}

Full UI review screenshots captured for all pages in the StockBot application after premarket activation and UI truth tranche.

## Screenshots Captured

${pages.map((p, i) => `${i + 1}. **${p.name}.png** - \`${p.path}\` - ${p.name}`).join('\n')}

## Key UI Updates

### Premarket Prep Center (formerly Intelligence Center)
- Premarket readiness header with session, scanner, scrappy, AI Referee, paper armed status
- Focus board showing scanner-ranked symbols with intelligence coverage
- Readiness status (ready/watch/stale/missing) for each focus symbol
- Automation status section

### AI Assessments (formerly AI Referee)
- Mode summary with enabled/disabled, mode, paper required status
- Focus symbols needing assessment section
- Enhanced assessments table with flags and rationale

### Command Center
- Premarket prep summary section
- Enhanced paper exposure with detailed lifecycle table
- Shows source, managed status, stop, target, protection, P&L for each position

### Navigation Labels Updated
- Intelligence → Premarket Prep
- AI Referee → AI Assessments
- Performance → Outcomes
- Experiments → Mode Analysis

## Capture Details
- **Date:** ${dateStr}
- **Time:** ${timeStr}
- **UI URL:** ${baseUrl}
- **Viewport:** 1920x1080
- **Full Page:** Yes
`;

  fs.writeFileSync(readmePath, readmeContent);
  console.log(`📝 README created: ${readmePath}`);
})();
