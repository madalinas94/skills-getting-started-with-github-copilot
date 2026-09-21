# PLAN.md — CSV Sales Dashboard

## Ce construim

O aplicație care primește **orice** CSV de vânzări — curat sau murdar — și în câteva
secunde scoate un dashboard interactiv: tabel curățat, grafice, cifre-cheie și un
asistent care răspunde în română la întrebări despre date. Codul calculează,
modelul explică. Niciodată invers.

## Arhitectură

```
┌─────────────┐   CSV    ┌──────────────────┐   JSON   ┌─────────────────┐
│   Browser    │ ───────▶ │  FastAPI backend │ ───────▶ │  Dashboard (JS)  │
│ (upload UI)  │          │                  │ ◀─────── │ tabel + Chart.js │
└─────────────┘          │  1. parse        │          └─────────────────┘
                          │  2. curățare     │
      ┌───────────────────  3. detect coloane
      │                   │  4. agregări     │
      ▼                   │  5. cache hash   │
┌──────────────┐          └────────┬─────────┘
│ Întrebare RO │                   │ rezumat numeric (nu CSV brut)
│ "/ask"       │ ─────────────────▶│
└──────────────┘          ┌────────▼─────────┐
                           │  LLM (explică)   │
                           └──────────────────┘
```

## Piesele aplicației

| # | Piesă | Tehnologie | Ce face |
|---|-------|-----------|---------|
| 1 | Upload | FastAPI `POST /upload` | Primește CSV-ul, îl salvează sub un hash (SHA-1 al conținutului) → cache automat, nu reprocesăm același fișier de două ori |
| 2 | Parsing tolerant | `pandas.read_csv` cu `sep=None, engine="python"` + fallback pe encoding (utf-8 → latin-1) | Detectează automat delimitatorul (`,` sau `;` — exporturile RO din Excel folosesc `;` fiindcă `,` e separator zecimal) și sare peste liniile de metadata dinaintea header-ului real (ex. "Generat automat la...", "NU MODIFICATI ACEST FISIER") căutând primul rând care arată ca un header de tabel |
| 3 | Curățare | pandas + regex | Elimină rânduri complet goale, convertește sume scrise ca text ("1.841,86" format RO → `1841.86`), normalizează monedă multiplă (RON/EUR — coloană `Valuta` păstrată separat, fără conversie inventată), unifică majuscule/minuscule inconsistente ("Livrata"/"LIVRATA"/"livrata" → o singură valoare canonică), scoate rândurile de total/subtotal intercalate ("TOTAL PARTIAL" — heuristică: primul câmp e text non-cod urmat de celule goale și o singură valoare numerică mult mai mare), elimină rândurile duplicate exact (același Nr. comandă + aceleași valori) |
| 4 | Deduplicare nume | `rapidfuzz` (similaritate ≥ 90%, case-insensitive) | "Delta Foods SA" / "DELTA FOODS SA" / "delta foods sa" → un singur nume canonic, cu listă de variante afișată la cerere |
| 5 | Detectare coloane | inferență pe tip + pe semantică (regex/dicționar de cuvinte-cheie: preț, cantitate, dată, regiune, produs) | Funcționează pe orice denumire de coloană, nu doar pe cea din exemplul nostru |
| 6 | Motor de agregare | cod Python pur (`pandas.groupby`), zero calcul lăsat pe model | Sumă, medie, min/max, count, top-N, trend lunar — toate deterministe și testabile |
| 7 | Detectare anomalii | `IQR`/`z-score` pe coloanele numerice | Semnalează outlieri (ex. o comandă de 50x peste medie) — "wow"-ul: dashboard-ul îți arată singur ce e ciudat în date |
| 8 | Tabel + grafice | `app.js` + Chart.js | Tabel paginat, sortabil; grafice (bar/line/pie) generate din agregatele din pasul 6, niciodată din date brute |
| 9 | Asistent RO | `POST /ask` | Trimite modelului doar rezumatul numeric (schema + agregate), nu tot CSV-ul → răspunsuri rapide, ieftine și fără halucinații de cifre |
| 10 | Robustețe | `pytest` + corpus de CSV-uri murdare (goale, cu sume text, nume duplicate, total intercalat, encoding greșit, coloane lipsă) | Fiecare regulă de curățare are un test dedicat |
| 11 | Deploy | FastAPI + statice, servite pe un link public, responsive (funcționează și pe telefon) | Un singur `git push` → live |

## Ce face aplicația "wow"

- **Nu presupune nimic despre CSV**: aceleași reguli funcționează pe fișiere complet diferite ca structură.
- **Se auto-explică**: la finalul procesării arată un mic raport ("am curățat 12 rânduri goale, am unificat 3 variante de nume, am găsit 2 valori anormale") — utilizatorul vede exact ce s-a întâmplat cu datele lui.
- **Cache pe hash**: reîncarci același CSV → răspuns instant, fără reprocesare.
- **Garanție de corectitudine**: toate cifrele afișate vin din pasul 6 (cod determinist, testat); modelul nu are voie să producă numere, doar interpretare în limbaj natural.

## Pași de urmat

1. **Setup proiect** — instalează dependențele (`fastapi`, `uvicorn`, `pandas`, `rapidfuzz`) și creează structura de foldere (`src/app.py`, `src/static/`).
2. **Endpoint upload** — `POST /upload`: primește CSV-ul, calculează hash SHA-1, salvează fișierul temporar.
3. **Parsing tolerant** — citește CSV-ul cu `pandas.read_csv` (auto-detect delimitator + fallback encoding utf-8/latin-1).
4. **Curățare date** — elimină rânduri goale, convertește sumele scrise ca text în numere, scoate rândurile de total intercalate.
5. **Deduplicare nume** — aplică `rapidfuzz` pentru a unifica variantele aceluiași nume (≥90% similaritate).
6. **Detectare coloane + agregări** — identifică automat coloanele (produs, dată, preț etc.) și calculează sumă/medie/min/max/top-N în cod Python (nu în model).
7. **Detectare anomalii** — marchează valorile outlier (IQR/z-score) pe coloanele numerice.
8. **Frontend (tabel + grafice)** — construiește `app.js`: tabel din datele curățate + grafice Chart.js din agregate.
9. **Endpoint /ask** — trimite întrebarea + rezumatul numeric (nu tot CSV-ul) către model, pentru răspunsuri în română fără cifre halucinate.
10. **Testare & deploy** — scrie teste `pytest` cu CSV-uri murdare, apoi publică aplicația pe un link public (funcțional și pe telefon).

## Date exemplu

- `sample_data/vanzari.csv` — produs, dată, cantitate, preț, regiune — cu rânduri goale, sume ca
  text și nume duplicate injectate intenționat.
- `sample_data/vanzari_2026.csv` — export real de tip "sistem intern": linii de
  metadata înainte de header, delimitator `;`, format numeric RO (`1.841,86`),
  monedă dublă (RON/EUR), status și client cu majuscule inconsistente, rânduri
  `TOTAL PARTIAL` intercalate și un rând de comandă duplicat exact.

## Livrabile

1. `PLAN.md` (acest fișier)
2. Linkul aplicației, funcțional pe orice CSV, inclusiv `vânzări.csv`
