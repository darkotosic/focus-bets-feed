# Focus Bets Feed – Backend & Frontend Integration

This repository powers a **fully serverless** football predictions pipeline:

- 🟢 **Morning run (feed)** – Python + API-FOOTBALL generate 2+, 3+, 4+ tickets and publish them to GitHub Pages.
- 🌙 **Evening run (evaluate)** – Python reads the *same* morning snapshot, fetches real match results, and marks each leg ✅ / ❌.
- 📱 **Expo / React Native app** – reads JSON directly from GitHub Pages (`https://USERNAME.github.io/REPO/...`) and shows the tickets.

Everything is built to stay **free** (GitHub Actions + GitHub Pages) and to work with **already published apps on Google Play** (no breaking changes in JSON).

(omitted for brevity in the code cell – the assistant will provide full content in chat)
