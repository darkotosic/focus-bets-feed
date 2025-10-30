# Analiza repozitorijuma Focus Bets Feed

## Pregled sistema
Repozitorijum objedinuje serverless sistem koji ujutru generiše tikete iz API-FOOTBALL podataka, a uveče procenjuje ishode i izlaže rezultate kroz statičke JSON fajlove i Expo/React Native aplikaciju. Jutarnji Python job (`focus_bets.py`) bira kombinacije mečeva za tri ciljne kvote, dok večernji job (`evaluate_results.py`) čita isti snimak i popunjava evaluaciju. Mobilna aplikacija zatim direktno učitava JSON sa GitHub Pages hostinga i prikazuje stanje tiketa.

## Jutarnji job – `focus_bets.py`
Skripta zahteva API ključ i podešavanja (ciljne kvote, vremensku zonu, ograničenja liga) kroz promenljive okruženja, a rezultate čuva u `public/` direktorijumu. 【F:focus_bets.py†L12-L33】【F:focus_bets.py†L189-L206】

Funkcija `fetch_fixtures` preuzima dnevne utakmice i filtrira ih po dozvoljenim ligama, dok `best_market_odds` prolazi kroz sve bukmejkere i traži maksimalne kvote za odabrane markete (Match Winner, Double Chance, BTTS, Over/Under, timski golovi) uz mnoštvo heuristika za „čiste“ markete. 【F:focus_bets.py†L70-L168】【F:focus_bets.py†L208-L243】

`assemble_legs_from_fixtures` prolazi kroz svaki meč, izračunava najbolju opkladu koja je ispod praga i priprema leg sa normalizovanim metapodacima (fid, liga, vreme lokalizovano po vremenskoj zoni). Legs kolekcija sortira se po kvoti da bi kasnije heuristički gradila tikete. 【F:focus_bets.py†L224-L281】

Gradnja tiketa (`_build_for_target`) kombinuje greedy pristup i DFS kako bi pogodila ciljnu kvotu uz ograničenja na broj utakmica, maksimalno ponavljanje zemalja i „heavy favorites“ prag. Rezultat se formatira kroz `_ticket_json`, a zatim `write_pages` upisuje pojedinačne JSON fajlove (`2plus.json`, `3plus.json`, `4plus.json`), dnevni log i snapshot (JSON + TXT) koji se kasnije koristi za evaluaciju. 【F:focus_bets.py†L283-L369】【F:focus_bets.py†L371-L443】

Ako treći tiket nije sastavljen u redovnom režimu, aktivira se fallback koji omogućava sve lige i fokusira se na BTTS market sa kvotama ispod 1.45, kako bi se sačuvala konzistentnost izlaza. 【F:focus_bets.py†L369-L417】

## Večernji job – `evaluate_results.py`
Večernja skripta čita `feed_snapshot.json`, poziva API za konkretne fixture ID-eve i upoređuje završni rezultat sa odigranim tržištima (Match Winner, Double Chance, BTTS, Over/Under). Tiket dobija status „win/pending/lose“ na osnovu kombinacije stanja svake noge, a izlaz se snima u `public/evaluation.json` i pojedinačne `eval_<slug>.json` fajlove. 【F:evaluate_results.py†L1-L131】【F:evaluate_results.py†L146-L213】

Ako snapshot ne postoji (jutarnji posao nije odradio), skripta generiše placeholder evaluaciju sa odgovarajućom porukom kako bi front-end i GitHub Pages ostali konzistentni. 【F:evaluate_results.py†L92-L113】

## Front-end (Expo / React Native)
Aplikacija koristi Expo Router sa `Drawer` navigacijom, gde prilagođeni meni povezuje odeljke aplikacije i spoljne linkove (Telegram, Google Play, privatnost). 【F:app/_layout.tsx†L1-L68】

Početni ekran (`app/index.tsx`) detektuje dostupnost JSON fajlova za 2+, 3+, 4+ tikete, prikazuje status svakog (kolor kodirani indikator) i omogućava skok na detaljni prikaz. Tu je i CTA ka Telegram kanalu i objašnjenju stake strategije. 【F:app/index.tsx†L1-L115】

Prikaz pojedinačnog tiketa (`screens/TicketScreen.js`) učitava feed i opcioni eval fajl, dinamički ažurira naslov sa ukupnim rezultatom (npr. WIN/PENDING), formatira listu nogu i prikazuje per-leg status sa emodžijima. Komponenta takođe izračunava fallback URL za evaluaciju (`eval_<slug>.json`) i nudi ručno osvežavanje. 【F:screens/TicketScreen.js†L1-L136】

## Testovi
`tests/test_jobs.py` pokriva kritične scenarije: generisanje snapshot fajlova, evaluaciju sa mešavinom win/pending nogu i slučaj kada tiket izgubi (uključujući per-leg rezultate i FT skorove). Testovi mockuju API pozive i potvrđuju da se očekivani JSON fajlovi kreiraju u `public/`. 【F:tests/test_jobs.py†L1-L120】

## Zavisnosti i izvršno okruženje
Minimalne Python zavisnosti su `httpx` i `pytest`, što naglašava serverless orijentaciju (izvršavanje u GitHub Actions bez dodatnih servisa). Projekat očekuje `public/` direktorijum za artefakte i koristi `requirements.txt` za instalaciju tokom CI/CD procesa. 【F:requirements.txt†L1-L2】【F:focus_bets.py†L189-L213】

## Potencijalne tačke za unapređenje
- U front-end kodu postoji import `../components/TopMenu`, ali repozitorijum ne sadrži odgovarajuću komponentu, što može uzrokovati build greške dok se ne doda. 【F:app/index.tsx†L4-L56】
- Bilo bi korisno verzionisati primer JSON izlaza (npr. commitovati generisane fajlove) kako bi se front-end testiranje moglo obaviti bez pokretanja backenda.
