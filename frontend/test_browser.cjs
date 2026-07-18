const { chromium } = require('playwright');

(async () => {
  console.log("Starting browser...");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err));

  console.log("Navigating to http://localhost:1420/...");
  await page.goto('http://localhost:1420/');
  
  console.log("Waiting 2s for load...");
  await page.waitForTimeout(2000);
  
  console.log("Dispatching arova-send...");
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('arova-send', { detail: { type: 'momentum.create_capsule' } }));
  });
  
  console.log("Waiting 2s for UI...");
  await page.waitForTimeout(2000);
  
  // Dump the HTML body
  const body = await page.innerHTML('body');
  console.log("BODY CONTAINS 'ContinuityErrorBoundary':", body.includes('ContinuityErrorBoundary'));
  console.log("BODY CONTAINS 'While you were away':", body.includes('While you were away'));
  console.log("BODY CONTAINS 'Error rendering':", body.includes('Error rendering'));
  
  await browser.close();
})();
