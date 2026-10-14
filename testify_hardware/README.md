# Testify Hardware — aplicația internă pentru calculul lunar

Aplicație web care rulează pe calculatorul de la birou și înlocuiește fișierele Excel.
Îi arată proprietarului, „la un click distanță”, câți bani intră, unde se duc, ce taxe
plătește firma și cât îi rămâne lui. Cotele de taxe se actualizează automat când se
schimbă Codul fiscal.

## Ce știe să facă

| Pagină | Ce conține |
| --- | --- |
| **Dashboard** | Venituri, costuri, profit și „cât îți rămâne ție” pe lună, cu comparație față de luna trecută; evoluția pe 12 luni; graficul „Unde se duc banii”; observații automate; top produse |
| **Vânzări** | Facturi pe produse din stoc (preț și cost se completează singure, numărul facturii e automat) sau doar totalul pe zi/lună; client, scadență și status încasat/neîncasat |
| **Stoc** | Produse cu cod, furnizor, preț, cost, stoc minim; stocul scade la vânzare și crește la recepția de marfă (NIR); alerte de stoc minim, „se termină în ~X zile”, fișa de inventar lunară |
| **Clienți** | Clienți B2B/B2C/marketplace cu termen de plată, vânzări pe client, facturi de încasat și restanțe |
| **Cheltuieli** | 19 categorii implicite, editabile: marfă, chirie, utilități, internet și telefonie, transport, combustibil, contabilitate, marketing, software, echipamente, comisioane bancare/POS, asigurări, reparații, ambalaje, taxe locale, SSM, training, protocol, altele |
| **Angajați** | Adăugare angajați, salariu brut cu istoric de măriri, calcul automat al netului și al costului pentru firmă, stat de plată lunar |
| **Taxe** | Decontul de TVA (colectată − deductibilă = de plată), CAS, CASS, impozit pe venit, CAM și impozitul pe profit, explicate pe înțeles, cu cotele valabile în luna aleasă |
| **Rapoarte** | Contul de profit și pierdere în structura raportului contabil, indicatori de control, export Excel (cu foi pentru vânzări, achiziții, cheltuieli, stocuri, salarii) și PDF |
| **Setări** | Firma, proprietarul, regimul de impozitare, plătitor de TVA, legislația fiscală (cu istoric), import din Excel/CSV, parola |

În plus:

- **Testi, asistentul:** un robot animat care îl salută pe proprietar la intrare, îi spune pe
  scurt cum a mers luna, îl avertizează când o cheltuială crește prea repede și îi explică
  noutățile fiscale în limbaj simplu.
- **Adăugare rapidă:** butonul „+ Adaugă” din colț, pentru o vânzare sau o cheltuială din câteva atingeri.
- **Versiune de telefon:** interfața se adaptează la ecranul mic, are meniu jos și se poate
  instala ca aplicație (vezi mai jos).

Cerințele clientului, pe scurt: un singur utilizator (proprietarul, Robert) protejat cu parolă,
impozit pe profit (nu e microîntreprindere), salarii stabilite la brut, doar vânzare de
accesorii, produse și inventar în aplicație, rulare pe calculatorul de la birou, separat de
site-ul firmei, cu acces de pe telefon.

**TVA:** clientul a spus inițial că nu plătește TVA, dar raportul contabilului calculează TVA
lunar (21%), iar la o cifră de afaceri de ~1,7 milioane lei pe an înregistrarea în scopuri de TVA
este obligatorie. Aplicația urmează raportul contabil (plătitor de TVA); setarea se poate
schimba din **Setări**.

## Datele firmei și verificarea cu contabilul

În `sample_data/` sunt fișierele primite de la firmă: raportul contabil pe T3 2026 (iulie–
septembrie), produsele, clienții, angajații, vânzările, cheltuielile și inventarul pe
septembrie. La prima pornire (sau din Setări) aplicația le poate încărca automat.

Calculele aplicației dau **exact aceleași cifre ca raportul contabilului** pentru fiecare lună:
venituri, costul mărfii vândute, marja brută, cheltuieli, profit, impozit pe profit, TVA de plată,
valoarea stocului, salarii și creanțe. Testele din `tests/test_client_data.py` verifică asta
automat. Pentru asta, aplicația folosește aceleași reguli ca statul de plată și raportul:
contribuțiile și impozitele se rotunjesc la leu (0,5 în sus), iar TVA se calculează pe fiecare document.

**Import:** din **Setări → Import din Excel / CSV** se pot aduce oricând fișiere noi. Tabelele
sunt recunoscute după coloane, iar ce există deja (aceeași factură, același NIR) nu se dublează.

## Pornire

Necesită Python 3.10 sau mai nou.

- **Windows:** dublu-click pe `start.bat`. Prima dată instalează tot ce trebuie, apoi deschide
  aplicația în browser.
- **macOS / Linux:** `./start.sh`, apoi deschideți <http://localhost:8000>.

La prima pornire alegeți parola. Dacă bifați „Încarcă datele firmei”, aplicația se umple cu
datele din T3 2026 primite de la firmă.

**De pe telefon:** cu telefonul conectat la Wi-Fi-ul de la birou, deschideți
`http://<adresa-IP-a-calculatorului>:8000` (adresa IP o vedeți cu `ipconfig` pe Windows), apoi
din meniul browserului alegeți „Adaugă pe ecranul principal”. Instalarea completă ca aplicație
(cu funcționare offline) cere o adresă HTTPS; pe calculatorul local (`localhost`) merge direct.

Datele se salvează în `data/testify.db`. Pentru o copie de siguranță, copiați acest fișier.

## Actualizarea automată a regulilor fiscale

Cotele de taxe nu sunt scrise în cod. Ele stau în fișierul `app/fiscal/ro.json`, în care
fiecare set de cote are **data de la care se aplică**:

- Aplicația descarcă singură versiunea publicată a acestui fișier, la pornire și apoi la fiecare
  6 ore. Adresa implicită este fișierul din acest repository, de pe ramura `main`; se poate
  schimba cu variabila de mediu `TESTIFY_FISCAL_FEED` (un șir gol oprește actualizarea).
- Când apare o regulă nouă, aplicația o salvează, recalculează lunile la care se aplică, iar
  Testi îl anunță pe proprietar ce s-a schimbat. O regulă poate fi publicată înainte să intre în
  vigoare (de exemplu în decembrie, pentru 1 ianuarie).
- Lunile trecute rămân calculate cu cotele valabile atunci (de exemplu, dividendele din 2025 cu
  10%, cele din 2026 cu 16%).
- Dacă nu există internet sau fișierul descărcat e invalid, aplicația păstrează ultimele reguli
  salvate și nu strică niciun calcul.

**Cine actualizează fișierul:** statul nu publică cotele într-un format pe care un program să-l
poată citi automat, iar textul legii nu poate fi interpretat automat în siguranță. De aceea,
când se schimbă legea, cine întreține aplicația adaugă o regulă nouă în `ro.json` și o publică.
De acolo, toate instalările se actualizează singure. Programele de facturare din România
funcționează la fel.

## Cum se calculează

- **Salariu:** CAS 25% și CASS 10% din brut; impozit pe venit 10% din (brut − CAS − CASS);
  firma plătește în plus CAM 2,25%. Costul pentru firmă = brut + CAM.
- **Marja brută** = venituri − costul mărfii vândute (cantitate × cost de achiziție). Marfa
  cumpărată intră în stoc și devine cost abia când se vinde.
- **Profit înainte de impozit** = marja brută − cheltuieli − salarii brute − CAM.
- **TVA de plată** = TVA din vânzări − TVA din achizițiile de marfă − TVA din cheltuieli
  (cote standard, redusă sau scutit, după tipul cheltuielii).
- **Impozit pe profit:** 16% din profitul înainte de impozit. Într-o lună pe pierdere nu se
  plătește. (Din Setări se poate trece pe regimul de microîntreprindere: 1% din venituri.)
- **Profit net** = profit înainte de impozit − impozit pe profit.
- **Îți rămâne ție** = profit net − impozitul pe dividende (16% din 2026).
- **Creanțe:** o factură către un client cu termen de plată rămâne „de încasat” până o marcați
  încasată; după scadență apare ca restantă.
- La luna în curs, comparația se face cu aceeași perioadă din luna trecută.

Calculul e o estimare lunară, pentru imaginea de ansamblu: nu ține cont de deducerea personală,
de facilitățile fiscale sau de recuperarea pierderilor din lunile anterioare la impozitul pe
profit (care legal se declară trimestrial). Cifrele oficiale rămân cele ale contabilului.

## Tehnic

- **Server:** Python, FastAPI, SQLite (`app/`); verificarea regulilor fiscale rulează în fundal
- **Interfață:** HTML, CSS și JavaScript simplu, cu grafice Chart.js (inclus local, merge și fără internet)
- **Telefon:** manifest de aplicație web și service worker (`app/static/manifest.webmanifest`, `sw.js`)
- **Export:** openpyxl (Excel), reportlab (PDF)
- **Teste:** `pip install -r requirements.txt && pytest`
