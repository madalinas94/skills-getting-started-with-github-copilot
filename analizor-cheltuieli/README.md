# Penny · Analizor de cheltuieli

**Penny** e robotul-asistent al aplicației (*your money buddy*). Te salută când deschizi aplicația, îți rezumă luna, îți dă atenționări și te învață cum să economisești.

Încarci exportul CSV de la card, extrasul de cont PDF și poze cu bonurile cash. Aplicația le pune într-un singur tabel curat (dată, descriere, sumă, monedă, categorie, sursă), arată un grafic pe categorii pentru luna aleasă și răspunde la întrebări în limbaj natural, de exemplu „Cât am cheltuit pe mâncare în martie?”.

**Stack:** Python + FastAPI (backend), HTML/CSS/JS simplu (frontend, fără build), Claude API (AI).

## Cum se pornește

```bash
cd analizor-cheltuieli
pip install -r requirements.txt
cp .env.example .env          # apoi pune cheia în ANTHROPIC_API_KEY=...
uvicorn backend.main:app --reload
```

Deschide http://localhost:8000. Penny te salută; apasă **„Arată-mi cu datele demo”** (încarcă dintr-un click fișierele din `fisiere-test/`) sau trage oriunde în pagină propriile fișiere.

- Testele merg fără cheie și fără cost: `python -m pytest -q`
- Fără cheie aplicația merge în continuare, dar în **mod local**. Categoriile se aleg prin reguli, întrebările sunt interpretate local, iar bonurile se introduc din formularul „Adaugă manual”.
- Modelul se schimbă din `.env` cu `CLAUDE_MODEL=...`. Implicit e `claude-opus-5-5`, cu effort `low`.

## Ce face

| Nivel | Implementare |
|---|---|
| 1 | Upload CSV → tabel curat. AI-ul alege categoria din lista fixă (un singur apel pentru tot fișierul). Întrebări în limbaj natural cu răspuns calculat exact |
| 2 | Extras PDF + bonuri foto (citite de Claude din imagine). Grafic pe categorii pentru luna aleasă (click pe o categorie filtrează tabelul) |
| 3 | Toate cele trei surse combinate, cu **deduplicare**: plățile cu cardul apar și în CSV, și în extras (Kaufland 312,80, eMAG 1.249,99, Enel 214,37). Sunt numărate o singură dată |

Monede: afișare în RON / EUR / USD (butoanele de sus) și filtru „Moneda tranzacției”. Fiecare tranzacție își păstrează moneda originală, care apare în coloana „Original”. Conversia folosește cursul fix 1 EUR = 5,25 RON și 1 USD = 4,40 RON.

Ecranele aplicației (4 taburi + chat):

| Tab | Ce conține |
|---|---|
| 🏠 **Acasă** | Penny cu rezumatul lunii, **scor financiar 0–100** (gauge), 5 KPI-uri (cheltuieli, încasări, sold, rată de economisire, economie posibilă), **donut pe categorii**, **atenționări** colorate pe severitate, **grafic zi cu zi** (bare + total cumulat), **regula 50/30/20** (ideal vs. tu), top sfaturi |
| 📊 **Analize** | Tabel calitativ **categorii vs. buget recomandat** (folosire buget + status *În buget / Atenție / Peste buget*), cheltuieli **pe zile ale săptămânii**, donut **pe surse de plată**, **top comercianți**, **abonamente** cu cost lunar și anual |
| 💡 **Sfaturi** | Potențialul total de economisire (pe lună și pe an), **10+ tipuri de recomandări** cu economie estimată și **tips bifabile** (progresul se ține minte), plus **sfaturi personalizate cu AI** la cerere |
| 🧾 **Tranzacții** | Upload, adăugare manuală, filtre (monedă, sursă, categorie, tip, căutare), tabel sortabil cu categorie editabilă, export CSV |
| 💬 **Chat Penny** | Buton flotant (sau tasta `/`): întrebări în limbaj natural, cu răspuns, defalcare și link spre tranzacțiile folosite |

Totul e interactiv: click pe o felie din donut, pe o zi din grafic sau pe un comerciant te duce direct la tranzacțiile respective. Are temă întunecată și luminoasă și funcționează pe telefon.

Funcții extra:
- corectezi categoria din tabel, iar corecția e reținută pentru viitor
- „Vezi tranzacțiile” arată exact rândurile folosite la un răspuns
- export CSV
- respinge un fișier deja încărcat, ca sumele să nu se dubleze
- contor de cost AI în header
- funcționează și fără AI

**Cifre de control (martie 2026, toate sursele):**
- Mâncare: 1.259,20 RON (1.185,70 pe card + 73,50 bon)
- Încasări: 6.700,42 RON
- Duplicate excluse: 3

## 3 decizii tehnice (problemă → soluție)

**1. Cifrele trebuie să fie corecte → AI-ul nu face niciodată calcule.**
Problemă: un LLM care adună 30 de sume poate greși, iar pentru 12 puncte cifrele trebuie să fie exacte.
Soluție: Claude transformă întrebarea într-un **filtru JSON** (operație, categorii, lună, tip, monedă, sursă), validat prin *structured outputs* pe o schemă fixă. Python aplică filtrul și calculează suma. Răspunsul e deci reproductibil, iar butonul „Vezi tranzacțiile” arată exact ce rânduri au intrat în calcul.

**2. Cost-effective → AI doar unde e nevoie, cu batch și cache.**
Problemă: dacă trimiți fiecare tranzacție sau tot tabelul la fiecare întrebare, costul crește odată cu datele.
Soluție, pe niveluri:
- **CSV și PDF se parsează determinist în cod**, cu cost zero. Pentru PDF, debitul/creditul se deduce din variația soldului. Claude primește PDF-ul doar dacă textul nu poate fi extras (de exemplu un PDF scanat).
- **Categorii:** un singur apel batch per upload, care conține doar comercianții *unici și necunoscuți* (normalizați: „MEGA IMAGE 0123” și „MEGA IMAGE 0456” sunt același comerciant). Rezultatul se salvează pe disc, deci la al doilea upload costul e zero (verificat în teste).
- **Întrebări:** Claude primește doar întrebarea și lista lunilor disponibile, nu tranzacțiile. Costul rămâne constant oricât de multe date ai. Întrebările repetate vin din cache.
- **Încasările** sunt marcate „Venituri” direct prin regulă, fără AI.
- System prompt-urile sunt fixe și marcate pentru *prompt caching*, iar effort-ul e `low`.

Costul real al unei sesiuni apare în header.

**Bonus · Recomandările sunt calculate local, AI-ul doar le personalizează.**
Atenționările, scorul, regula 50/30/20 și cele 10+ tipuri de recomandări se calculează în Python (`backend/insights.py`) cu reguli transparente. Sunt gratuite, instantanee și reproductibile. Butonul „Sfaturi personalizate cu AI” trimite către Claude **doar totaluri agregate** (pe categorii, top comercianți), niciodată tranzacții individuale. E mai ieftin și protejează datele. Răspunsul se cachează pentru aceleași cifre.

**3. Date murdare și surse care se suprapun → normalizare + deduplicare.**
Problemă: CSV-ul amestecă 4 formate de dată (`2026-03-04`, `05/03/2026`, `6.03.2026`, `3 mar. 2026`), sume cu separator de mii (`1.249,99`), BOM, rânduri de titlu și un subsol „Total inregistrari”. Pe lângă asta, plățile cu cardul apar și în extras, iar CSV-ul conține și zile din februarie și aprilie.
Soluție:
- parser tolerant, cu antetul detectat automat
- separatorul zecimal ales după poziție
- rândurile fără dată validă sunt ignorate
- tranzacțiile din extras care au aceeași sumă, aceeași monedă și o dată la cel mult ±3 zile de o tranzacție din CSV (plus același comerciant, aceeași zi sau „Plata card”) sunt marcate ca duplicat și excluse din totaluri. Ele rămân vizibile tăiat, cu bifa „arată duplicatele”
- filtrul pe lună se aplică pe data reală, așa că 27 februarie și 1 aprilie nu intră în martie
- încasările (credit) nu sunt niciodată socotite cheltuieli

## Structură

```
backend/parsers.py      CSV + PDF → tranzacții (fără AI)
backend/categorize.py   cache → AI batch → reguli de rezervă
backend/ai.py           toate apelurile Claude (categorii, bonuri, întrebări)
backend/store.py        stocare, deduplicare, conversie valutară, calcule
backend/local_query.py  interpretare întrebări fără AI (rezervă)
backend/insights.py     scor, atenționări, recomandări, regula 50/30/20, tabele
backend/main.py         API FastAPI
static/                 interfața (Penny + grafice SVG proprii, fără biblioteci)
tests/                  26 de teste, inclusiv totalurile verificate de mână
```
