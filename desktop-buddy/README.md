# Desktop Buddy — Mady

Mady, un roboțel-fetiță șatenă cu codițe, care stă pe desktop. O poți muta oriunde cu mouse-ul,
iar când dai click pe ea se deschide un panou mic (ca un tray) cu:

- **📋 Clipboard** – salvează automat tot ce copiezi (Ctrl+C). Click pe un element îl copiază înapoi.
  Poți fixa (📍), salva ca notiță (📝), șterge și căuta.
- **📝 Notițe** – notițe cu salvare automată și căutare.
- **🤖 Asistent AI** – chat cu un agent AI. Providerul, modelul și cheia API se aleg din Setări.
- **⏱ Timer** – sesiuni de lucru cu titlu. Un timer mic, mereu deasupra, pe care îl muți oriunde,
  cu pauză, stop, opacitate și ascundere. La fiecare oră primești „1 Hour has passed”, iar la final
  un raport cu timpul total, timpul activ și aplicațiile folosite (plus feedback de la Mady).
  Secțiunea **Workdays** arată ultimele 30 de zile ca un calendar (ore lucrate, sesiuni, top aplicații),
  iar graficul săptămânal compară cu săptămâna trecută.
- **✉ Inbox** – citește ultimele emailuri din Gmail prin IMAP (fără să le marcheze ca citite),
  cu **Rezumat** pentru fiecare email și **Quick brief** pentru tot inboxul, făcute de modelul AI din Setări.
- **⚙️ Setări** – provider AI, model, API key (salvată criptat), system prompt, numele și mărimea
  roboțelului, „mereu deasupra”, pornire cu Windows, clipboard, temă.

## Azi: planner-ul zilei

Primul tab din panou, inspirat din planner-ele „aesthetic” de productivitate:

- **Salut personalizat** și **intenția zilei** („calm, clar, curajos”).
- **Top 3 priorități** cu bife rotunde. Când le termini pe toate, Mady sărbătorește.
- **Ritualuri (habit tracker):** săptămâna ca puncte aurii, cu serii („3 zile”); ritualurile se adaugă și se șterg liber.
- **Apă** (8 pahare), **stare** (radiantă / bine / ok / obosită / stresată) și **recunoștință**.
- **Citatul zilei** (Seneca, da Vinci, Buffett, Audrey Hepburn…).
- **Obiective:** primele 3 obiective cu progres și următorul pas; **Ritualul de seară** se deschide de aici.
- **Împărtășește:** cardul **„Ziua mea”** sau **„Săptămâna mea”**, în format **Post 4:5** (1080×1350) sau
  **Story 9:16** (1080×1920), salvat în `Imagini\Desktop Buddy` și copiat cu un click, gata de pus pe Instagram.

## Mantra zilei

La fiecare pornire, un card elegant apare separat, în colțul din dreapta-sus, cu **mesajul zilei**,
și dispare singur după 30 de secunde (se oprește cât ții mouse-ul pe el; durata se schimbă din Setări).
În fiecare zi alt tip: **citat**, **cuvântul zilei** (ex: Sprezzatura, Ikigai, Kaizen), **motivație**,
**idee filozofică** (stoici, Aristotel…) sau **vorbă de duh**. Cu un model AI conectat, Mady o scrie
în stilul ei; altfel alege dintr-o colecție atent aleasă. Rămâne aceeași toată ziua.
Din card: ♡ favorită, **Imagine** (story 9:16 salvat și copiat), **Azi**. O găsești și în tab-ul Azi
(„Pe desktop” o readuce), în meniul lui Mady și în tray.

## Vision board

Fereastră separată în stil Pinterest: fotografiile tale ca polaroid-uri cu bandă washi și legendă,
plus carduri de text (noir, blush, ivory, sage). Adaugi imagini din buton sau trăgându-le din Explorer,
le reordonezi, le ștergi, schimbi titlul. **Exportă** creează o imagine 1080×1350 pentru Instagram.
Imaginile se copiază în folderul aplicației, deci rămân chiar dacă muți originalele.

**Ariile vieții:** butonul „Ariile vieții” creează secțiuni pentru Călătorii, Succes, Cărți,
Libertate financiară, Mașina visurilor, Casa mea, Iubire adevărată, Credință și rugăciune, Frumusețe,
Fit și sănătoasă, Eleganță și rafinament, Familia împreună. Fiecare are un cadru cu o ilustrație
aurie (click sau trage o fotografie peste el ca să-l umpli) și o afirmație pe care o poți schimba
(⟳). Filtrele de sus arată o singură arie.

**Imagini reale de pe internet:** „Imagini reale” (sau bifa din fereastra ariilor) umple automat
cadrele cu fotografii găsite pe internet, pe căutări în registrul „old money” (Amalfi, manor englezesc,
bibliotecă clasică, Mercedes vintage, perle și mătase…). Pe fiecare poză: ⟳ altă imagine. Cu un filtru
activ, căutarea ariei se poate schimba (ex: „Range Rover Autobiography”). Sub fiecare fotografie apare
autorul și licența. Sursa se alege din Setări → Vision board: **Openverse** (fără cheie, licențe
Creative Commons), **Pexels** sau **Unsplash** (cheie gratuită, fotografii editoriale), sau
**Google Imagini** (cheie Google Cloud pentru Custom Search JSON API + ID-ul unui motor de căutare cu
căutare de imagini activă).

**Din Google, fără nicio cheie:** butonul **G** de pe fiecare cadru (sau „Caută pe Google” din bara
de căutare a ariei) deschide Google Imagini în browser, cu căutarea ariei. Alegi poza și:
- o **tragi** direct peste cadru (sau oriunde pe board), sau
- click dreapta → **Copiază imaginea**, apoi butonul **Lipește** de pe cadru (sau **Ctrl+V** pe board).
Merg și linkurile Google copiate („imgres?imgurl=…”), linkurile directe la imagini și miniaturile. Afirmațiile apar și ca **„Afirmația zilei”** în mantra zilei.

## Obiective cu progres

Vision board-ul devine plan: **Obiectivele mele** (din Azi → „Toate obiectivele”, din tray sau de pe
insigna unei arii din vision board) urmărește trei tipuri de obiective, fiecare legat de o arie a vieții:

- **Bani (fonduri):** fondul de libertate financiară, fondul de siguranță, avansul pentru casă,
  mașina visurilor, călătoriile. Adaugi contribuții (sau +50 / +100 / +250 / +500 dintr-un click),
  iar Mady calculează **ritmul necesar pe lună** până la termen și, din ritmul ultimelor 3 luni,
  **luna în care ajungi** („✓ la timp” sau „mărește puțin contribuția”). Pentru libertatea financiară
  există un **calculator cu regula de 4%** (cheltuieli lunare × 12 × 25). Nu e sfat financiar personalizat.
- **Număr:** 24 de cărți, 150 de antrenamente, km alergați, cu progres și ritm pe lună.
- **Etapă:** „Vacanță cu toată familia”, cu pași de bifat și „Marchează ca atins”.

Fiecare obiectiv are un inel de progres, **pașii următori** (checklist) și un rezumat sus: fonduri
economisite din total, obiective active, pași bifați săptămâna asta, obiective atinse. La **25%, 50%, 75%
și 100%** apare confetti aurie, iar Mady te felicită. În tab-ul **Azi** vezi primele 3 obiective cu
următorul pas (bifabil direct de acolo), pe **vision board** fiecare afirmație primește o insignă cu
progresul ariei, iar **briefingul de dimineață** amintește obiectivul principal și ritmul lui.

## Ritualul de seară

Un jurnal elegant (copertă de piele în culoarea temei, hârtie liniată) în patru pagini:

1. **Ce a mers bine** – cu statisticile zilei (focus, priorități, ritualuri, apă, pași și contribuții
   la obiective), prioritățile bifate deja trecute pe listă și o notă a zilei (1–5 stele).
2. **Ce am învățat** – cu începuturi de frază („Despre bani și piețe…”, „Despre mine…”).
3. **Recunoștință și rugăciune** – afirmația zilei din aria Credință, o rugăciune scurtă de seară și bifa
   „Am spus rugăciunea de seară”.
4. **Mâine** – intenția și Top 3 pentru mâine, precompletate cu ce a rămas nebifat azi. Dimineață le
   găsești direct în tab-ul Azi, iar briefingul pornește de la ele.

La final, Mady îți scrie un **gând de noapte bună** (cu modelul AI din Setări, sau din șablon în modul
demo), iar „Cardul zilei” creează imaginea pentru Instagram. **Jurnalele trecute** se văd oricând.
La ora aleasă (implicit 21:00, Setări → Mady) Mady te invită printr-o bulă și o notificare; invitația
vine o singură dată pe seară și doar dacă ești la calculator.

## Raport lunar

În Timer → „Luna aceasta”: ore de focus, zile lucrate, media pe zi, cea mai bună zi. Cardul
**„Luna mea”** (post sau story) adaugă calendarul lunii colorat după ore, procentul fiecărui ritual,
prioritățile bifate, stările, apa și mantra preferată a lunii.

## Heritage (tema implicită)

Varianta cea mai matură și luxoasă: hârtie ivory cu textură fină de in, cerneală bleumarin, accente
oxblood și alamă, titluri în majuscule mici între linii fine, rame cu linie dublă, colțuri drepte.
Mady poartă un **coc elegant**, cercei cu perle și un **blazer bleumarin** cu nasturi de alamă
(Setări → Mady → Coafura: „Codițe” pentru varianta jucăușă).

## Teme sezoniere

**Paris · toamnă** (burgundy și coniac, Mady cu beretă), **Viena · iarnă** (bleumarin și șampanie, cu
fular), **Riviera · vară** (albastru mediteranean și lămâie, cu ochelari de soare), **Florența ·
primăvară** (salvie și rose gold, cu coroniță de flori). **Sezonier automat** schimbă tema după anotimp.

## Focus mode

- La pornirea unei sesiuni alegi **Liber**, **Pomodoro 25/5**, **Deep work 50/10** sau **Flow 90/20**.
- Inel de progres, runde marcate cu puncte aurii; la final de rundă, pauza pornește singură (sesiunea se
  oprește, deci statisticile numără doar focusul), cu pauză lungă după 4 runde. Mady te anunță la fiecare
  trecere; timerul plutitor arată „Focus · runda 2” sau „Pauză” și timpul rămas.
- **Sunete de focus:** ploaie, zgomot maro, ocean, șemineu. Sunt generate în aplicație (fără fișiere audio), cu volum.

## Prima pornire

Un ghid de bun venit în 3 pași: cum să-ți spună Mady, obiectivul săptămânal și trucurile de bază.
Se poate relua din Setări → **Ghid de bun venit**.

## Sticky notes

Orice notiță poate fi lipită pe desktop (butonul **Pe desktop** din editor, butonul cu notiță din
tab-ul Notițe, sau din meniul lui Mady / tray: **Notiță nouă pe desktop**).

- **Hârtie:** ivory, blush, sage, champagne, powder blue, bordeaux, noir; **decor:** bandă washi, pioneză aurie,
  agrafă sau simplu; titlu serif italic și rânduri fine, ca pe o foaie de jurnal.
- Le muți trăgând de marginea de sus/jos, le redimensionezi din colțul din dreapta-jos, le restrângi
  la titlu, le ții mereu deasupra sau le dezlipești (notița rămâne în panou și revine cu același aspect).
- Textul se sincronizează în ambele sensuri cu tab-ul Notițe. Poziția, mărimea și stilul rămân
  după repornire. „Arată notițele lipite” din tray le aduce pe toate în față.

## Mady e vie

- **Stări:** e concentrată (ochi îngustați) cât rulează o sesiune, adoarme (zzz) după 5 minute fără
  activitate, sărbătorește (sclipiri aurii, sare) la final de sesiune și la briefing, și se alarmează (!)
  când vin emailuri importante. Face cu mâna când treci cu mouse-ul peste ea.
- **Bule de dialog:** îți vorbește în stilul ei la începutul și finalul sesiunilor, la fiecare oră, când
  vin emailuri, când revii la calculator, plus replici spontane (artă, finanțe, filozofie). Click pe
  bulă deschide secțiunea potrivită. Se pot opri din Setări → Mady.
- **Briefing de dimineață:** la prima activitate din zi îți pregătește în chat: emailurile importante de
  ieri seară încoace, câte ore ai lucrat în ultima zi, progresul față de obiectivul săptămânal și
  prioritatea zilei. Opțional ți-l citește cu voce tare (voce românească dacă e instalată în Windows).
  Butonul ☀ din tab-ul Asistent îl generează oricând.
- **Ctrl+Shift+Space (din orice aplicație):** o fereastră rapidă „Întreab-o pe Mady” pentru întrebări
  și pentru textul copiat: **Corectează**, **Rezumă**, **Traduce** (RO/EN/ES/FR/IT/DE) și **Mai elegant**
  (pentru emailuri). Rezultatul se copiază cu un click. Scurtătura se poate schimba din Setări.
  Aceleași acțiuni sunt și pe fiecare element din Clipboard (butonul ✦).

## Teme

- **Old Money · Ivory** (implicit) – ivory, verde englezesc și auriu, fonturi serif clasice;
  Mady poartă rochiță verde cu tiv auriu, fundițe crem și colier de perle.
- **Old Money · Evening** – aceeași eleganță, pe fundal verde-noapte.
- **Bordeaux & aur** – catifea vișinie și aur pe hârtie crem: antet bordeaux cu monogramă aurie,
  linii duble aurii, butoane vișinii; Mady poartă o rochie de catifea bordeaux cu broderie aurie și perle.
  Tema se aplică peste tot: panou, timer, mantra, vision board, obiective și jurnalul de seară.
- **Roz · luminos / întunecat** – look-ul original, cu Mady în rochiță roz.

Fonturile (Cormorant Garamond, EB Garamond, licență SIL OFL 1.1) sunt incluse în
`renderer/fonts/`, deci aplicația arată la fel și fără internet.

Click dreapta pe roboțel → meniu rapid (Notițe, AI, Setări, Ascunde, Ieșire).
Aplicația apare și în system tray (lângă ceas).

## Rulare în mod dezvoltare

```bash
cd desktop-buddy
npm install
npm start
```

## Crearea fișierului .exe (Windows)

Pe un calculator cu Windows:

```bash
cd desktop-buddy
npm install
npm run dist
```

În `desktop-buddy/dist/` vor apărea:

- `Desktop Buddy Setup 1.0.0.exe` – installer; creează iconița pe Desktop și în Start Menu.
- `DesktopBuddy-Portable-1.0.0.exe` – un singur .exe; dublu-click și pornește, fără instalare.

**Fără Windows la îndemână:** workflow-ul GitHub Actions `Build Desktop Buddy (.exe)` construiește
automat ambele fișiere la fiecare push pe `desktop-buddy/`. Le descarci din tab-ul **Actions** →
ultimul run → secțiunea **Artifacts** → `DesktopBuddy-windows`.

## Inbox (Gmail)

1. Activează **2-Step Verification** pe contul Google.
2. Creează o **parolă de aplicație** la https://myaccount.google.com/apppasswords.
3. În Gmail → Setări → *Forwarding and POP/IMAP*, verifică să fie activ **IMAP**.
4. În Desktop Buddy → Setări → Inbox: adresa de email + parola de aplicație (server `imap.gmail.com`, port `993`).

**Scanare automată:** la fiecare oră (configurabil: 30 min – 4 ore) Mady verifică inboxul și îți
arată o notificare Windows cu câte emailuri necitite ai primit azi și care sunt cele mai importante.
În tab-ul Inbox găsești rezumatul complet făcut de AI, ora ultimei scanări și a următoarei, plus
butonul „Scanează acum”. Click pe notificare deschide direct Inbox-ul.

Parola se păstrează criptat. Emailurile sunt ținute doar în memorie. Pentru rezumate, textul
emailurilor e trimis providerului AI ales în Setări (în modul Demo nu pleacă nicăieri).

## Timer: cum se detectează aplicațiile

Pe Windows, în timpul unei sesiuni, aplicația citește la 5 secunde numele programului din
prim-plan (printr-un proces PowerShell ascuns, fără module native). Timpul în care nu atingi
mouse-ul/tastatura peste 5 minute e numărat ca „inactiv”. Se poate opri din Setări → Timer.
Calendarul arată ultimele 30 de zile; istoricul se păstrează mai mult, pentru raportul lunar.

## Agentul AI (placeholder)

Implicit e activ providerul **Demo** – răspunde fără internet, doar ca să vezi cum arată.
Din Setări → Asistent AI poți alege:

| Provider | Ce trebuie completat |
|---|---|
| Anthropic (Claude) | model + API key |
| OpenAI | model + API key |
| Custom (compatibil OpenAI) | Base URL + model (+ API key dacă serviciul cere) |

Modelele din listă sunt doar sugestii; alege „Alt model (scriu eu)…” pentru orice alt nume.
Codul providerilor e în `src/ai.js`. Când decizi ce serviciu folosești, acolo adaugi/modifici
providerul.

Cheia API se păstrează criptat cu `safeStorage` (DPAPI pe Windows) în
`%APPDATA%/Desktop Buddy/buddy-data.json`, împreună cu notițele și istoricul clipboard.

## Structură

```
desktop-buddy/
├── main.js            # procesul principal: ferestre, tray, clipboard, IPC
├── preload.js         # API-ul sigur expus către HTML (window.buddy)
├── src/store.js       # salvare date în JSON + criptarea cheii API
├── src/ai.js          # providerii AI (demo / Anthropic / OpenAI / custom)
├── src/sessions.js    # sesiuni, reminder orar, rapoarte, istoric 30 zile
├── src/activity.js    # detectarea aplicației din prim-plan
├── src/mail.js        # citire inbox prin IMAP + prompturi pentru rezumat/brief
├── src/mailscan.js    # scanarea automată orară + notificarea
├── src/mood.js        # stările lui Mady și replicile ei
├── src/briefing.js    # briefingul de dimineață
├── src/today.js       # planner-ul zilei: Top 3, ritualuri, apă, stare, citate
├── src/cards.js       # cardurile de Instagram (zi, săptămână, lună, mantra), randate offscreen în PNG
├── src/mantra.js      # mantra zilei (AI sau colecție), favorite
├── src/vision.js      # vision board: imagini, carduri de text, ariile vieții
├── src/lifeareas.js   # ariile vieții și afirmațiile lor
├── src/goals.js       # obiective cu progres: fonduri, număr, etape, ritm și dată estimată
├── src/evening.js     # ritualul de seară: jurnal, gând de noapte bună, planul de mâine
├── src/imagesearch.js # căutare și descărcare de imagini (Openverse / Pexels / Unsplash)
├── renderer/sticky.*  # notițele lipite pe desktop
├── renderer/          # HTML/CSS/JS pentru roboțel și panou
├── assets/            # buddy.svg, icon.svg, icon.png, icon.ico
└── scripts/make-ico.js# regenerează icon.ico din assets/icons/*.png
```
