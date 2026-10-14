# Testify Hardware — aplicația internă pentru calculul lunar

Aplicație web care rulează pe calculatorul de la birou și înlocuiește fișierele Excel.
Îi arată proprietarului, „la un click distanță”, câți bani intră, unde se duc, ce taxe
plătește firma și cât îi rămâne lui. Cotele de taxe se actualizează automat când se
schimbă Codul fiscal.

## Cum o deschideți (pe scurt)

1. **Instalați Python** (gratuit) de pe <https://www.python.org/downloads/>. Pe Windows, la
   instalare bifați **„Add python.exe to PATH”**.
2. **Descărcați aplicația:** pe această pagină, butonul verde **Code → Download ZIP**, apoi
   dezarhivați folderul (sau `git clone` dacă folosiți Git).
3. **Porniți-o:** pe Windows, dublu-click pe **`start.bat`**; pe Mac/Linux, rulați `./start.sh`
   în terminal. Prima pornire durează un minut (instalează ce îi trebuie).
4. Aplicația se deschide în browser la <http://localhost:8000>. La prima intrare alegeți parola,
   notați codul de recuperare și bifați „Încarcă datele firmei” ca să vedeți datele din T3 2026.
5. **Opțional, Testi cu AI:** Setări → Testi cu inteligență artificială → lipiți cheia API
   Anthropic primită separat (cheia nu se pune niciodată în acest repository).

## Ce știe să facă

| Pagină | Ce conține |
| --- | --- |
| **Dashboard** | Venituri, costuri, profit și „cât îți rămâne ție” pe lună, cu comparație față de luna trecută; evoluția pe 12 luni; graficul „Unde se duc banii”; observații automate; top produse |
| **Vânzări** | Facturi pe produse din stoc (preț și cost se completează singure, numărul facturii e automat) sau doar totalul pe zi/lună; client, scadență și status încasat/neîncasat |
| **Stoc** | Produse cu cod, furnizor, preț, cost, stoc minim; stocul scade la vânzare și crește la recepția de marfă (NIR); alerte de stoc minim, „se termină în ~X zile”, fișa de inventar lunară |
| **Clienți** | Clienți B2B/B2C/marketplace cu termen de plată, vânzări pe client, facturi de încasat și restanțe |
| **Furnizori** | Furnizori cu termen de plată (implicit 30 de zile), marfă cumpărată, plăți de făcut în ordinea scadenței, restanțe și ce e scadent în 7 zile |
| **Cheltuieli** | 19 categorii implicite, editabile: marfă, chirie, utilități, internet și telefonie, transport, combustibil, contabilitate, marketing, software, echipamente, comisioane bancare/POS, asigurări, reparații, ambalaje, taxe locale, SSM, training, protocol, altele |
| **Angajați** | Adăugare angajați, salariu brut cu istoric de măriri, calcul automat al netului și al costului pentru firmă, stat de plată lunar |
| **Taxe** | Decontul de TVA (colectată − deductibilă = de plată), CAS, CASS, impozit pe venit, CAM și impozitul pe profit, explicate pe înțeles, cu cotele valabile în luna aleasă |
| **Rapoarte** | Contul de profit și pierdere în structura raportului contabil, indicatori de control, export Excel (cu foi pentru vânzări, achiziții, cheltuieli, stocuri, salarii) și PDF |
| **Setări** | Firma, proprietarul, regimul de impozitare, plătitor de TVA, legislația fiscală (cu istoric), import din Excel/CSV, parola |

În plus:

- **Testi, asistentul:** un robot animat care îl salută pe proprietar la intrare, îi spune pe
  scurt cum a mers luna, îl avertizează când o cheltuială crește prea repede și îi explică
  noutățile fiscale în limbaj simplu.
- **Testi cu AI (opțional):** din **Setări → Testi cu inteligență artificială**, cu o cheie API
  Anthropic, Robert poate pune întrebări libere („De ce a scăzut profitul în august?”, „Ce produse
  să comand?”). Răspunsurile vin de la modelul Claude (`claude-opus-5-5`), pe baza unui rezumat al
  datelor firmei trimis la fiecare întrebare. Fără cheie, opțiunea nu apare și aplicația rămâne
  complet locală. Vedeți secțiunea „Asistentul AI” de mai jos.
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

La prima pornire alegeți parola și primiți un **cod de recuperare** (de forma `ABCD-EFGH-JKMN-PQRS`),
pe care îl notați pe hârtie, îl salvați ca fișier sau îl printați. Dacă uitați parola, pe ecranul de
intrare apăsați „Am uitat parola”, introduceți codul și alegeți o parolă nouă; codul folosit expiră și
primiți automat unul nou. Din **Setări** se poate genera oricând un cod nou (cu parola actuală).
După 5 încercări greșite la rând, intrarea se blochează 5 minute. Dacă bifați „Încarcă datele firmei”, aplicația se umple cu
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

## Asistentul AI (opțional)

- **Pornire:** Setări → bifați „Activează asistentul AI” și lipiți cheia API Anthropic (din
  console.anthropic.com). Cheia se poate da și prin variabila de mediu `ANTHROPIC_API_KEY`.
- **Ce se trimite:** la fiecare întrebare, un rezumat JSON cu lunile (venituri, costuri, profit,
  TVA), stocul, clienții, furnizorii, angajații și salariile, plus ultimele mesaje din conversație.
  Parola, codul de recuperare și cheia API nu se trimit niciodată.
- **Cost și internet:** fiecare întrebare consumă din contul Anthropic (rezumatul are ~3.000 de
  tokeni) și cere conexiune la internet. Instrucțiunile fixe sunt marcate pentru cache, ca să coste mai puțin.
- **Siguranță:** cheia se păstrează local, în baza de date a aplicației, și nu se afișează niciodată
  întreagă în interfață. Dacă modelul refuză o întrebare, o preia automat modelul de rezervă
  recomandat de Anthropic (`fallbacks: "default"`).
- **Teste:** `tests/test_ai.py` folosește un client simulat, deci rulează fără cheie și fără cost.

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
- **Datorii la furnizori:** fiecare recepție de marfă primește scadența după termenul
  furnizorului (clientul plătește la 15–30 de zile) și rămâne „de plătit” până o marcați plătită.
- **Alerte de stoc:** fiecare produs are un stoc minim (implicit 5 bucăți pentru produsele noi);
  sub el, alerta apare în aplicație: la Testi, pe dashboard, la emiterea facturii și în pagina Stoc.
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
