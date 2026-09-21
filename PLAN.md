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
| 2 | Parsing tolerant | `pandas.read_csv` cu `sep=None, engine="python"` + fallback pe encoding (utf-8 → latin-1) | Nu pică la delimitator greșit sau encoding ciudat |
| 3 | Curățare | pandas + regex | Elimină rânduri complet goale, convertește sume scrise ca text ("1.234,56 lei" → `1234.56`), scoate rândurile de total/subtotal intercalate (heuristică: rând unde >50% din celulele numerice lipsesc dar una e mult mai mare decât vecinii) |
| 4 | Deduplicare nume | `rapidfuzz` (similaritate ≥ 90%) | "Popescu Ion" / "ION POPESCU" / "I. Popescu" → un singur nume canonic, cu listă de variante afișată la cerere |
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

## Date exemplu

`vânzări.csv` — produs, dată, cantitate, preț, regiune — cu rânduri goale, sume ca
text și nume duplicate injectate intenționat, pentru a demonstra curățarea.

## Livrabile

1. `PLAN.md` (acest fișier)
2. Linkul aplicației, funcțional pe orice CSV, inclusiv `vânzări.csv`
