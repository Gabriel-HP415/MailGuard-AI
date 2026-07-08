const { chromium } = require('playwright');
const path = require('path');

const extensionPath = path.resolve(__dirname, '../chrome_extension');

async function main() {
  console.log('Starting E2E Chrome Extension Test...');
  
  // Launch persistent context with extension loaded
  const browserContext = await chromium.launchPersistentContext('', {
    headless: false, // E2E testing of chrome extension requires headed mode
    slowMo: 800,     // Slow down actions by 800ms so you can observe them
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      '--disable-web-security',
      '--allow-running-insecure-content',
    ],
  });

  // Enable context-wide logging of page console output and errors
  browserContext.on('page', page => {
    page.on('console', msg => {
      // Filter out noisy warnings or info if preferred, but show all for debugging
      console.log(`[PAGE LOG] [${page.url()}]: ${msg.text()}`);
    });
    page.on('pageerror', err => {
      console.error(`[PAGE ERROR] [${page.url()}]: ${err.stack || err.message}`);
    });
  });

  try {
    // Wait for the background service worker
    console.log('Waiting for background service worker...');
    let [backgroundPage] = browserContext.serviceWorkers();
    if (!backgroundPage) {
      backgroundPage = await browserContext.waitForEvent('serviceworker');
    }
    console.log('Service worker loaded:', backgroundPage.url());

    // Extract extension ID
    const extensionId = backgroundPage.url().split('/')[2];
    console.log('Detected Extension ID:', extensionId);

    // Open options page
    const optionsPage = await browserContext.newPage();
    const optionsUrl = `chrome-extension://${extensionId}/options/options.html`;
    console.log('Navigating to options page:', optionsUrl);
    await optionsPage.goto(optionsUrl);

    // Verify initial load
    await optionsPage.waitForSelector('#auth-pill');
    
    // Fill configuration and credentials
    console.log('Configuring backend URL and legacy credentials...');
    await optionsPage.fill('#base-url', 'http://127.0.0.1:8003/api/v1');
    // Trigger the change event on base-url input to save it
    await optionsPage.dispatchEvent('#base-url', 'change');
    
    await optionsPage.fill('#email', 'admin@mailguard.ai');
    await optionsPage.fill('#password', 'ChangeMe123!');
    
    console.log('Clicking sign in...');
    await optionsPage.click('button[value="login"]');

    // Wait for auth pill to change to Online
    console.log('Waiting for auth status to become Online...');
    await optionsPage.waitForFunction(() => {
      const pill = document.getElementById('auth-pill');
      return pill && pill.textContent.trim() === 'Online';
    }, { timeout: 10000 });

    const authStatusText = await optionsPage.textContent('#auth-status');
    console.log('Authentication successful:', authStatusText);
    await optionsPage.waitForTimeout(2000); // Pause for 2s to observe options status

    // Now test content script injection by navigating to a mocked mail.google.com page
    console.log('Setting up mock page for mail.google.com...');
    const mailPage = await browserContext.newPage();

    // Enable routing to mock Gmail body
    await mailPage.route('https://mail.google.com/mail/u/0/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: `
          <!DOCTYPE html>
          <html>
            <head>
              <title>Mock Gmail Inbox</title>
            </head>
            <body>
              <div id="gmail-inbox-container">
                <h1>Gmail Inbox Mock</h1>
                <div id="email-view-root">
                  <!-- Email container will be dynamically loaded to trigger the MutationObserver -->
                </div>
              </div>
            </body>
          </html>
        `
      });
    });

    console.log('Navigating to mock Gmail URL...');
    await mailPage.goto('https://mail.google.com/mail/u/0/');

    // Check if content scripts are loaded
    const globals = await mailPage.evaluate(() => {
      return {
        hasApi: typeof window.MailGuardAPI !== 'undefined',
        hasScraper: typeof window.GmailScraper !== 'undefined',
        hasHighlighter: typeof window.MailGuardHighlighter !== 'undefined',
        url: window.location.href
      };
    });
    console.log('Checked globals on mailPage:', globals);

    // Now dynamically insert an email body into the mock page.
    // This will trigger the extension's MutationObserver
    console.log('Simulating email opening by inserting DOM elements...');
    await mailPage.evaluate(() => {
      const root = document.getElementById('email-view-root');
      root.innerHTML = `
        <div role="main">
          <div style="margin-bottom: 10px;">
            <span class="gD" email="security@paypa1.com">PayPal Security Team</span>
          </div>
          <h2 class="hP">URGENT: Verify your account now or it will be suspended</h2>
          <div class="a3s aiL">
            Dear Customer,
            Your account has been temporarily suspended due to suspicious activity.
            Click http://paypa1-secure.com/verify to confirm your identity.
            Please verify within 24 hours.
          </div>
        </div>
      `;
    });

    // Wait for the MailGuard-AI banner to be rendered by the content script
    console.log('Waiting for MailGuard-AI banner to appear...');
    const bannerSelector = '#__mailguard_banner__';
    await mailPage.waitForSelector(bannerSelector, { timeout: 15000 });

    console.log('Banner detected!');
    const verdictText = await mailPage.textContent(`${bannerSelector} .mg-banner__pill`);
    const riskText = await mailPage.textContent(`${bannerSelector} .mg-banner__risk`);
    const summaryText = await mailPage.textContent(`${bannerSelector} .mg-banner__summary`);
    
    console.log(`Verdict: ${verdictText}`);
    console.log(`Risk: ${riskText}`);
    console.log(`Summary: ${summaryText}`);

    if (!verdictText.includes('SCAM')) {
      throw new Error(`Expected verdict SCAM but got ${verdictText}`);
    }

    // Check highlighted spans
    console.log('Checking highlight marks inside the email body...');
    const highlightsCount = await mailPage.locator('.mg-mark').count();
    console.log(`Found ${highlightsCount} highlight marks`);
    for (let i = 0; i < highlightsCount; i++) {
      const markText = await mailPage.locator('.mg-mark').nth(i).textContent();
      const markTitle = await mailPage.locator('.mg-mark').nth(i).getAttribute('title');
      console.log(`  Highlight ${i+1}: "${markText}" -> Reason: "${markTitle}"`);
    }

    // Click "This is correct" feedback button
    console.log('Clicking "This is correct" feedback button...');
    await mailPage.click('button[data-mg-action="correct"]');

    // Wait for the success toast to be displayed by MailGuardUI
    console.log('Waiting for feedback toast to appear...');
    const toastSelector = '#__mailguard_toast_container__ div';
    await mailPage.waitForSelector(toastSelector, { timeout: 5000 });
    const toastText = await mailPage.textContent(toastSelector);
    console.log('Feedback Toast message:', toastText);
    
    if (!toastText.includes('Thanks for your feedback')) {
      throw new Error(`Expected feedback success toast, got: ${toastText}`);
    }

    console.log('Waiting 5 seconds so you can observe the UI before closing...');
    await mailPage.waitForTimeout(5000); // Pause for 5s to observe Gmail banner and toast

    console.log('\n[PASS] Chrome Extension E2E test completed successfully!');
  } catch (error) {
    console.error('\n[FAIL] E2E test failed:', error);
    process.exitCode = 1;
  } finally {
    await browserContext.close();
  }
}

main();
