import type { Page } from "@playwright/test";

export async function installSyntheticAddressBar(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const BAR_ID = "routedeck-playwright-address-bar";
    const URL_VALUE_ID = "routedeck-playwright-address-value";

    const updateAddress = () => {
      const value = document.getElementById(URL_VALUE_ID);
      if (value !== null) value.textContent = window.location.href;
    };

    const mountAddressBar = () => {
      if (document.getElementById(BAR_ID) !== null) {
        updateAddress();
        return;
      }

      document.documentElement.dataset.routedeckRecordingFrame = "true";
      const style = document.createElement("style");
      style.dataset.routedeckRecordingStyle = "true";
      style.textContent = `
        html[data-routedeck-recording-frame="true"] {
          overflow: hidden !important;
          --routedeck-recording-bar-height: 52px;
        }

        html[data-routedeck-recording-frame="true"] body {
          min-height: 100vh !important;
          min-height: 100dvh !important;
          overflow: hidden !important;
          padding-top: var(--routedeck-recording-bar-height) !important;
        }

        html[data-routedeck-recording-frame="true"] .buyer-app {
          height: calc(100vh - var(--routedeck-recording-bar-height)) !important;
          height: calc(100dvh - var(--routedeck-recording-bar-height)) !important;
        }

        html[data-routedeck-recording-frame="true"] .bootstrap-loading {
          inset: var(--routedeck-recording-bar-height) 0 0 !important;
        }

        #${BAR_ID} {
          position: fixed;
          z-index: 2147483647;
          inset: 0 0 auto;
          display: grid;
          height: var(--routedeck-recording-bar-height);
          grid-template-columns: auto minmax(0, 1fr) auto;
          align-items: center;
          gap: 14px;
          border-bottom: 1px solid #3c4043;
          background: #202124;
          padding: 7px 14px;
          box-shadow: 0 1px 5px rgb(0 0 0 / 28%);
          color: #e8eaed;
          font-family: Inter, "Segoe UI", system-ui, sans-serif;
          pointer-events: none;
        }

        #${BAR_ID} .routedeck-recording-controls {
          display: flex;
          align-items: center;
          gap: 13px;
          color: #bdc1c6;
          font-size: 19px;
          line-height: 1;
        }

        #${BAR_ID} .routedeck-recording-address {
          display: grid;
          min-width: 0;
          height: 36px;
          grid-template-columns: auto minmax(0, 1fr);
          align-items: center;
          gap: 9px;
          border: 1px solid #5f6368;
          border-radius: 18px;
          background: #303134;
          padding: 0 13px;
          box-shadow: inset 0 1px 1px rgb(0 0 0 / 12%);
        }

        #${BAR_ID} .routedeck-recording-site-info {
          display: grid;
          width: 18px;
          height: 18px;
          place-items: center;
          border: 1px solid #9aa0a6;
          border-radius: 50%;
          color: #bdc1c6;
          font-size: 11px;
          font-weight: 700;
        }

        #${URL_VALUE_ID} {
          min-width: 0;
          overflow: hidden;
          color: #f1f3f4;
          font-family: "Roboto Mono", Consolas, ui-monospace, monospace;
          font-size: 14px;
          font-weight: 400;
          letter-spacing: -0.01em;
          line-height: 20px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        #${BAR_ID} .routedeck-recording-badge {
          border: 1px solid #5f6368;
          border-radius: 999px;
          padding: 4px 9px;
          color: #bdc1c6;
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
      `;
      document.head.append(style);

      const bar = document.createElement("div");
      bar.id = BAR_ID;
      bar.dataset.testid = "synthetic-address-bar";
      bar.setAttribute("aria-label", "Synthetic Playwright browser address bar");
      bar.innerHTML = `
        <span class="routedeck-recording-controls" aria-hidden="true">
          <span>←</span><span>→</span><span>↻</span>
        </span>
        <span class="routedeck-recording-address">
          <span class="routedeck-recording-site-info" aria-hidden="true">i</span>
          <span id="${URL_VALUE_ID}" data-testid="synthetic-address-value"></span>
        </span>
        <span class="routedeck-recording-badge">Playwright · live local</span>
      `;
      document.body.prepend(bar);
      updateAddress();
    };

    const historyMethods = ["pushState", "replaceState"] as const;
    for (const method of historyMethods) {
      const original = window.history[method].bind(window.history);
      Object.defineProperty(window.history, method, {
        configurable: true,
        value: (...args: Parameters<History["pushState"]>) => {
          original(...args);
          queueMicrotask(updateAddress);
        },
      });
    }
    window.addEventListener("popstate", updateAddress);
    window.addEventListener("hashchange", updateAddress);

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountAddressBar, {
        once: true,
      });
    } else {
      mountAddressBar();
    }
  });
}
