# 🤖 GitHub Agents – Focus Bets Feed

Ovaj dokument opisuje automatizovane **GitHub Actions agente** koji svakodnevno upravljaju
generisanjem i evaluacijom AI fudbalskih tiketa u repozitorijumu **focus-bets-feed**.

---

## 🕕 Morning Agent — `feed.yml`

**Funkcija:** generiše dnevni JSON feed i objavljuje ga na GitHub Pages.

### Koraci
1. Pokreće se automatski svakog dana u **06:00 UTC (07:00 Beograd)** ili ručno preko *Run workflow*.
2. Izvršava `focus_bets.py` koji:
   - povlači podatke iz API-FOOTBALL,
   - generiše tikete 2+, 3+, 4+ (uz fallback BTTS < 1.45),
   - snima rezultate u `public/`:
     - `2plus.json`
     - `3plus.json`
     - `4plus.json`
     - `daily_log.json`
     - `feed_snapshot.json`
     - `feed_snapshot.txt`
   - svaki leg sadrži tačan **Fixture ID (FID)** u formatu `YYYY-MM-DD HH:MM • FID`
3. Uploaduje dva artefakta:
   - **standardni** artifact `github-pages` (za večernju evaluaciju)
   - **GitHub Pages** artifact (za javni prikaz)

### Output
Objavljeno na:
`https://darkotosic.github.io/focus-bets-feed/`

---

## 🌙 Evening Agent — `evaluate.yml`

**Funkcija:** koristi jutarnji snapshot i označava ishode ✅ / ❌.

### Koraci
1. Pokreće se svakog dana u **20:30 UTC (21:30 Beograd)** ili ručno.
2. Preuzima jutarnji artifact `github-pages` koji sadrži `public/` sa feedom.
3. Pokreće `evaluate_results.py` / `evaluate_ticket.py`, koji:
   - čita `public/feed_snapshot.json` (jutarnji tiket)
   - za svaki FID radi `GET /fixtures?id={fid}`
   - proverava tipove: Match Winner, Double Chance, BTTS, Over/Under
   - dodaje ✅/❌ pored svakog para i ✅ pored total odds ako su svi pogođeni
4. Upisuje rezultat u `public/evaluation.json`
5. Ponovo uploaduje `public/` i deploy na GitHub Pages.

---

## 📦 Struktura public/

- `2plus.json`
- `3plus.json`
- `4plus.json`
- `daily_log.json`
- `feed_snapshot.json`  ← ključni most jutro → veče
- `feed_snapshot.txt`   ← ljudski čitljiv log
- `evaluation.json`     ← večernji rezultat

---

## 💾 Workflows

### `.github/workflows/pages.yml`

- generiše feed
- uploaduje **dva** artefakta (standardni + pages)
- koristi ga jutarnji run

### `.github/workflows/eval.yml`

- preuzima jutarnji standardni artifact
- pokreće evaluaciju nad ISTIM fixture-id vrednostima
- uploaduje nazad evaluirani public/

---

## 🔐 Secrets

- `API_FOOTBALL_KEY` – obavezno
- `API_FOOTBALL_URL` – opciono, ako koristiš custom endpoint
- ostalo (timezone, targets) podešeno u samom workflow-u

---

## 🧠 Napomena

Ovaj sistem je napravljen tako da **frontend ne mora da se menja** čak i kad se API ili backend logika promene.
Svi podaci koji su aplikaciji potrebni (posebno fixture_id i evaluacija) ulaze iz `public/` fajlova koji se svakog
dana iznova grade i objavljuju.
