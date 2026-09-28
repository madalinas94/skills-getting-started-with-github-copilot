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

## Sticky notes

Orice notiță poate fi lipită pe desktop (butonul **Pe desktop** din editor, butonul cu notiță din
tab-ul Notițe, sau din meniul lui Mady / tray: **Notiță nouă pe desktop**).

- **Hârtie:** ivory, blush, sage, champagne, powder blue, noir; **decor:** bandă washi, pioneză aurie,
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
Istoricul se păstrează 30 de zile.

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
├── renderer/sticky.*  # notițele lipite pe desktop
├── renderer/          # HTML/CSS/JS pentru roboțel și panou
├── assets/            # buddy.svg, icon.svg, icon.png, icon.ico
└── scripts/make-ico.js# regenerează icon.ico din assets/icons/*.png
```
