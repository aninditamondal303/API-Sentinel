# Screenshots

The images in this folder were captured from the real running application (the Docker Compose stack on `127.0.0.1`), not mocked or edited. The main [README](../../README.md) shows them in its Screenshots section.

## Captured

| File | What it shows |
|---|---|
| `01-landing.jpg` | Landing page with the product introduction and its illustrative example card |
| `02-compatibility.jpg` | Compatibility scan of the Orders API, `v1.4.0` → `v2.0.0`: failed decision, 17 findings, 9 breaking, severity breakdown |
| `03-finding-detail.jpg` | An expanded "Response property type changed" finding: impact, remediation, before (`number`) and after (`string`) values |
| `04-security.jpg` | Security scan of `v2.0.0`: passed, with the specification-level notice and one informational finding |
| `05-contract-tests.jpg` | Contract-test preview for `v1.4.0`: 4 operations (1 ready, 3 skipped with reasons), generated files and the ZIP download button |

How they were taken:
- Browser viewport 1024 × 768 px, saved at 800 px wide (JPEG).
- A fresh demo account named "Demo User" with the placeholder address `demo.user@example.com`. No real personal data, tokens or `.env` values are visible.
- Data comes from uploading `examples/orders-api/baseline.yaml` as `v1.4.0` and `examples/orders-api/candidate-breaking.yaml` as `v2.0.0`, then running the scans through the UI with the default project policy.
- The app's fade-in animations were switched off in the browser before each capture (an injected CSS rule), so text is not caught half-faded. Nothing else on the page was changed.

## Still to capture

| Suggested file | Page | Notes |
|---|---|---|
| `06-dashboard.png` | Dashboard after the scans above | A window of about 1440 × 900 shows all four statistic cards and both charts side by side |
| `07-mobile.png` (optional) | Any page at 375 px wide | Browser dev tools device mode; shows the mobile layout and menu button |

To capture them:
1. Start the stack: `powershell -ExecutionPolicy Bypass -File .\scripts\demo-backend.ps1` and wait for `0 failed check(s)`.
2. Open <http://127.0.0.1:3000>, sign in with a demo account that uses an `example.com` address, and repeat the steps above if the account has no data yet.
3. Wait about a second after each page loads so the fade-in finishes, then capture the browser viewport only.
4. Save the file here and add it to the README's Screenshots section.

Before committing images, check that no real email address, token (browser dev tools, `sessionStorage`) or `.env` value is visible, and keep each image under about 500 KB.
