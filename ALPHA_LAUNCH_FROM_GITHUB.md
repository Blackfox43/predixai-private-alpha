# PredixAI Private Alpha: GitHub Launch Guide

This ZIP is prepared for a private alpha deployment from GitHub.

## 1. Push to GitHub

```bash
git init
git add .
git commit -m "Prepare PredixAI private alpha"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

Create the alpha branch:

```bash
git checkout -b alpha-release
git push -u origin alpha-release
```

## 2. Validate locally

```bash
npm ci
npm run lint
npm run build
npm run check:python
```

For local server testing:

```bash
cp .env.example .env
# Edit .env and add GEMINI_API_KEY.
npm start
```

Open `http://localhost:3000`.

## 3. Deploy to Render

Create a new Render Web Service from your GitHub repo.

Use:

```text
Branch: alpha-release
Build command: npm ci && npm run build
Start command: npm start
```

Set these Render environment variables:

```text
NODE_ENV=production
GEMINI_API_KEY=your_real_server_side_key
GEMINI_MODEL=gemini-2.5-flash
ALPHA_ACCESS_PASSWORD=long_random_password
```

If `ALPHA_ACCESS_PASSWORD` is set, the app uses HTTP Basic Auth in production. Testers may enter any username; the password must match `ALPHA_ACCESS_PASSWORD`.

## 4. Pre-invite checks

```text
[ ] App loads
[ ] Chat works
[ ] No Gemini API key appears in browser source or dist files
[ ] Password gate blocks unauthenticated users
[ ] Dashboard, backtesting, and live tracking tabs load
[ ] Predictions display home/draw/away correctly
[ ] Alpha disclaimer is visible
```

Check for leaked keys locally after build:

```bash
grep -R "YOUR_REAL_GEMINI_KEY" dist/ || echo "No key found in dist"
```

## 5. Invite only 5-10 testers first

Send testers the private alpha URL and the password separately. Remind them predictions are experimental and not betting or financial advice.
