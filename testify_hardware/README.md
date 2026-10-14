# Testify Hardware — aplicația internă pentru calculul lunar

Aplicație web care rulează pe calculatorul de la birou și înlocuiește fișierele Excel.
Îi arată proprietarului, „la un click distanță”, câți bani intră, unde se duc, ce taxe
plătește firma și cât îi rămâne lui.

## Ce știe să facă

| Pagină | Ce conține |
| --- | --- |
| **Dashboard** | Venituri, costuri, profit și „cât îți rămâne ție” pe lună, cu comparație față de luna trecută; evoluția pe 12 luni; graficul „Unde se duc banii”; observații automate; top produse |
| **Vânzări** | Se adaugă fie fiecare comandă (produs, cantitate, preț), fie doar totalul pe zi/lună |
| **Cheltuieli** | 19 categorii implicite, editabile: marfă, chirie, utilități, internet și telefonie, transport, combustibil, contabilitate, marketing, software, echipamente, comisioane bancare/POS, asigurări, reparații, ambalaje, taxe locale, SSM, training, protocol, altele |
| **Angajați** | Adăugare angajați, salariu brut cu istoric de măriri, calcul automat al netului și al costului pentru firmă, stat de plată lunar |
| **Taxe** | CAS, CASS, impozit pe venit, CAM și impozit micro, explicate pe înțeles |
| **Rapoarte** | Export Excel și PDF pentru contabilă, plus comparația pe ultimele 12 luni |
| **Setări** | Numele firmei, cotele de taxe (modificabile dacă se schimbă legea), parola, date demo |

Cerințele clientului, pe scurt: un singur utilizator (proprietarul) protejat cu parolă,
firmă neplătitoare de TVA, salarii stabilite la brut, doar vânzare de accesorii, rulare pe
calculatorul de la birou, separat de site-ul firmei, cu acces opțional de pe telefon.

## Pornire

Necesită Python 3.10 sau mai nou.

- **Windows:** dublu-click pe `start.bat`. Prima dată instalează tot ce trebuie, apoi deschide
  aplicația în browser.
- **macOS / Linux:** `./start.sh`, apoi deschideți <http://localhost:8000>.

La prima pornire alegeți parola. Dacă bifați „Încarcă date demonstrative”, aplicația se umple
cu un an de activitate fictivă, bun pentru prezentare.

**De pe telefon:** cu telefonul conectat la Wi-Fi-ul de la birou, deschideți
`http://<adresa-IP-a-calculatorului>:8000` (adresa IP o vedeți cu `ipconfig` pe Windows).

Datele se salvează în `data/testify.db`. Pentru o copie de siguranță, copiați acest fișier.

## Cum se calculează

- **Salariu:** CAS 25% și CASS 10% din brut; impozit pe venit 10% din (brut − CAS − CASS);
  firma plătește în plus CAM 2,25%. Costul pentru firmă = brut + CAM.
- **Impozit microîntreprindere:** 1% din veniturile lunii.
- **Profit net** = venituri − cheltuieli − costul salariilor − impozit micro.
- **Îți rămâne ție** = profit net − impozitul pe dividende (16%).
- La luna în curs, comparația se face cu aceeași perioadă din luna trecută.

Toate cotele se pot modifica din **Setări**. Calculul nu ține cont de deducerea personală
și nici de alte facilități fiscale.

## Tehnic

- **Server:** Python, FastAPI, SQLite (`app/`)
- **Interfață:** HTML, CSS și JavaScript simplu, cu grafice Chart.js (inclus local, merge și fără internet)
- **Export:** openpyxl (Excel), reportlab (PDF)
- **Teste:** `pip install -r requirements.txt && pytest`
