# PredixAI Private Alpha Build

This repository contains the updated private-alpha version of PredixAI. It includes:

- Server-side Gemini chat endpoint; the API key is no longer exposed to the browser.
- Optional production HTTP Basic Auth gate via `ALPHA_ACCESS_PASSWORD`.
- Safer dashboard fetch/error handling.
- Refactored ML/backtesting critical files.
- GitHub Actions alpha CI workflow.
- Render deployment blueprint.
- Visible private-alpha disclaimer in the UI.

## Quick Start

```bash
npm ci
npm run lint
npm run build
npm run check:python
cp .env.example .env
# edit .env and add your GEMINI_API_KEY
npm start
```

See `ALPHA_LAUNCH_FROM_GITHUB.md` for the full GitHub-to-private-alpha launch steps.

---

## Original README

<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/6fec31a6-1c29-4d2b-b8c5-925f62acbd68

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`
