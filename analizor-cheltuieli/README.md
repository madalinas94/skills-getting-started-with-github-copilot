# Finn · your money sidekick

**Finn** e un robot-asistent pentru bani. Încarci exportul CSV de la card, extrasul de cont PDF și poze cu bonurile plătite cash. Finn le curăță, le categorisește cu AI și le combină fără dubluri. Apoi îți arată unde se duc banii, îți spune **povestea lunii** în slide-uri animate, îți dă atenționări și sfaturi de economisire, și răspunde la întrebări în limbaj natural (scrise sau vorbite).

🇷🇴 Română / 🇬🇧 English · 📱 merge pe telefon ca o aplicație (PWA) · 🌗 temă întunecată / luminoasă

**Stack:** Python + FastAPI (backend), HTML/CSS/JS fără framework și fără build (frontend), grafice SVG desenate de mână (fără biblioteci), Claude API (AI).

## Cum se pornește

```bash
cd analizor-cheltuieli
pip install -r requirements.txt
cp .env.example .env          # apoi pune cheia în ANTHROPIC_API_KEY=...
uvicorn backend.main:app --reload
```

Deschide http://localhost:8000. Finn te salută. Apasă **„Arată-mi cu datele demo”** (încarcă dintr-un click fișierele din `fisiere-test/`) sau trage oriunde în pagină propriile fișiere.

- **Pe telefon:** pornește cu `uvicorn backend.main:app --host 0.0.0.0` și deschide `http://<IP-ul-calculatorului>:8000` din aceeași rețea Wi-Fi. Interfața are bară de navigare jos, chat tip bottom-sheet și tabel transformat în carduri. Ca s-o instalezi ca aplicație („Add to Home Screen”), browserul cere HTTPS, deci e nevoie de un tunel HTTPS (de exemplu ngrok sau cloudflared). Pe `localhost`, instalarea merge direct.
- **Testele** merg fără cheie și fără cost: `python -m pytest -q` (28 de teste).
- **Fără cheie**, aplicația merge în continuare în **mod local**: categorii prin reguli, întrebări interpretate local (RO și EN), bonuri introduse manual.
- **Modelul** se schimbă din `.env` cu `CLAUDE_MODEL=...`. Implicit e `claude-opus-5-5`, cu effort `low`.

## Ce face

| Nivel | Implementare |
|---|---|
| 1 | Upload CSV → tabel curat (dată, descriere, sumă, monedă, categorie, sursă). AI-ul alege categoria din lista fixă, cu un singur apel pentru tot fișierul. Întrebări în limbaj natural cu răspuns calculat exact |
| 2 | Extras PDF + bonuri foto (citite de Claude din imagine). Grafice pe categorii pentru luna aleasă |
| 3 | Toate cele trei surse combinate, cu **deduplicare**: plățile cu cardul apar și în CSV, și în extras (Kaufland 312,80, eMAG 1.249,99, Enel 214,37). Sunt numărate o singură dată |

**Monede:** afișare în RON / EUR / USD și filtru pe moneda originală. Fiecare tranzacție își păstrează moneda; conversia folosește cursul fix 1 EUR = 5,25 RON și 1 USD = 4,40 RON.

### Ecranele

| | Ce conține |
|---|---|
| 🏠 **Acasă** | Finn cu rezumatul lunii și starea lui (zâmbește sau e îngrijorat, după scor), **scor financiar 0–100**, 5 KPI-uri animate, **donut pe categorii**, **personalitatea ta financiară**, **atenționări**, **calendar-heatmap** al cheltuielilor, **grafic zi cu zi** (bare + cumulat), **regula 50/30/20**, top sfaturi |
| ▶ **Povestea lunii** | Slide-uri pe tot ecranul, ca un recap de tip *Wrapped*: cât ai cheltuit, categoria preferată, cea mai mare cheltuială, ziua cea mai scumpă, comerciantul preferat, abonamentele pe an, cât ai putea economisi și „personalitatea” lunii, la final cu confetti și buton de share. Navighezi cu tap, swipe sau săgeți; ții apăsat ca să pui pauză |
| 📊 **Analize** | Tabel calitativ **categorii vs. buget recomandat** (cu status *În buget / Atenție / Peste buget*), cheltuieli pe zile ale săptămânii, plăți pe surse, top comercianți, abonamente (lunar și anual) |
| 🎛️ **Simulator** | *„Ce-ar fi dacă…”*: glisoare pe fiecare categorie și scenarii rapide (Ușor / Inteligent / Hardcore). Vezi pe loc economia pe lună, pe an și în 5 ani. Îți setezi un **obiectiv** (de exemplu o vacanță) și vezi în câte luni îl atingi, plus ce-ți poți permite cu economia de un an |
| 💡 **Sfaturi** | 10+ tipuri de recomandări cu economie estimată și **pași bifabili** (progresul se ține minte), plus **sfaturi personalizate cu AI** la cerere |
| 🧾 **Tranzacții** | Upload, adăugare manuală, filtre, tabel sortabil cu categorie editabilă (Finn ține minte corecția), export CSV |
| 💬 **Chat Finn** | Întrebări scrise sau **prin voce** 🎙️, în română sau engleză. Răspunsul vine cu defalcare și link spre tranzacțiile folosite |

Totul e interactiv: click pe o felie, o zi din calendar sau un comerciant te duce direct la tranzacțiile respective. Robotul urmărește cursorul cu privirea.

**Cifre de control (martie 2026, toate sursele):**
- Mâncare: 1.259,20 RON (1.185,70 pe card + 73,50 bon)
- Încasări: 6.700,42 RON
- Duplicate excluse: 3

## 3 decizii tehnice (problemă → soluție)

**1. Cifrele trebuie să fie corecte → AI-ul nu face niciodată calcule.**
Problemă: un LLM care adună 30 de sume poate greși, iar trainerul verifică cifrele.
Soluție: Claude transformă întrebarea (RO sau EN) într-un **filtru JSON** (operație, categorii, lună, tip, monedă, sursă), validat prin *structured outputs*. Python aplică filtrul și calculează. Răspunsul e reproductibil, iar „Vezi tranzacțiile” arată exact rândurile folosite.

**2. Cost-effective → AI doar unde e nevoie, cu batch și cache.**
- **CSV-ul și PDF-ul se parsează determinist**, cu cost zero. Debitul sau creditul din PDF se deduce din variația soldului. Claude primește PDF-ul doar dacă textul nu se poate extrage (de exemplu un PDF scanat).
- **Categorii:** un singur apel batch per upload, doar pentru comercianții *unici și necunoscuți*. Rezultatul se salvează pe disc, iar la un nou upload costul e zero.
- **Întrebări:** Claude primește doar întrebarea, nu tranzacțiile, deci costul nu crește cu datele. Întrebările repetate vin din cache.
- **Recomandările, scorul, personalitatea, atenționările și povestea lunii** se calculează local, gratuit și instant.
- **Sfaturile personalizate cu AI** primesc doar totaluri agregate și se cachează.
- **Prompt caching** pe system prompt-urile fixe și effort `low`.

Costul real al sesiunii apare în header.

**3. Date murdare și surse care se suprapun → normalizare + deduplicare.**
CSV-ul amestecă 4 formate de dată (`2026-03-04`, `05/03/2026`, `6.03.2026`, `3 mar. 2026`), sume cu separator de mii (`1.249,99`), BOM, rânduri de titlu și un subsol „Total inregistrari”. Plățile cu cardul apar și în extras, iar CSV-ul are și zile din februarie și aprilie.
Soluție:
- parser tolerant, cu antetul detectat automat
- rândurile fără dată validă sunt ignorate
- deduplicare card ↔ extras după sumă, monedă și dată (±3 zile)
- filtrul pe lună se aplică pe data reală
- încasările nu sunt niciodată socotite cheltuieli
- același fișier încărcat de două ori e respins

### Alte alegeri

- **Bilingv fără dublarea logicii:** categoriile rămân stocate cu ID-ul din enunț, iar doar afișarea se traduce. Serverul generează textele (recomandări, răspunsuri) în limba cerută, iar cifrele sunt identice (verificat în teste).
- **Mobil ca o aplicație:**
  - PWA: manifest, service worker, merge offline
  - bară de navigare jos, chat tip bottom-sheet
  - safe-area pentru iPhone
  - pe ecrane mici, efectele grele (blur) sunt simplificate ca scroll-ul să fie fluid

## Structură

```
backend/parsers.py      CSV + PDF → tranzacții (fără AI)
backend/categorize.py   cache → AI batch → reguli de rezervă
backend/ai.py           toate apelurile Claude (categorii, bonuri, întrebări, sfaturi)
backend/store.py        stocare, deduplicare, conversie valutară, calcule, răspunsuri RO/EN
backend/insights.py     scor, atenționări, recomandări, personalitate, regula 50/30/20
backend/local_query.py  interpretare întrebări fără AI (RO + EN)
backend/i18n.py         traduceri pentru textele generate de server
backend/main.py         API FastAPI (+ manifest și service worker pentru PWA)
static/i18n.js          dicționarul RO / EN al interfeței
static/finn.js          robotul Finn (SVG animat, ochi care urmăresc cursorul, stări) + confetti
static/charts.js        donut, gauge, grafic zilnic, coloane, calendar-heatmap (SVG propriu)
static/story.js         „Povestea lunii”
static/app.js           logica interfeței
tests/                  28 de teste, inclusiv totalurile verificate de mână și RO/EN
```
