# PLAN.md

1. Upload CSV — endpoint FastAPI (`POST /upload`) primește fișierul (ex. `vânzări.csv`) și îl salvează temporar.
2. Citire & curățare — pandas: elimină rânduri goale, convertește sumele scrise ca text în numere, unifică nume scrise în mai multe feluri, scoate rândurile de total intercalate.
3. Detectare coloane — pandas infer dtypes (numeric, categoric, dată) automat, fără presupuneri fixe despre coloanele CSV-ului.
4. Calcule — cod Python (nu modelul): sumă, medie, min/max, count pe coloanele detectate (ex. vânzări pe produs/regiune/lună).
5. Tabel — rezultatul curățat, expus ca JSON de backend și randat ca tabel HTML în `src/static/index.html` + `app.js`.
6. Grafice — Chart.js în frontend, alimentat cu agregatele calculate de backend (nu date brute).
7. Întrebări în română — endpoint `POST /ask`: trimite întrebarea + rezumatul numeric (nu tot CSV-ul) către model; modelul explică, codul calculează.
8. Date exemplu — `vânzări.csv` (produs, dată, cantitate, preț, regiune) pentru dezvoltare și teste locale.
9. Robustețe — teste pytest cu CSV murdar: rânduri goale, sume ca text, nume duplicate, rânduri de total.
10. Livrare — aplicație FastAPI + fișiere statice, link public, funcțional și pe telefon.
