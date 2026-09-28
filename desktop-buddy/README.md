# Desktop Buddy — Mady

Mady, un roboțel-fetiță șatenă cu codițe, care stă pe desktop. O poți muta oriunde cu mouse-ul,
iar când dai click pe ea se deschide un panou mic (ca un tray) cu:

- **📋 Clipboard** – salvează automat tot ce copiezi (Ctrl+C). Click pe un element îl copiază înapoi.
  Poți fixa (📍), salva ca notiță (📝), șterge și căuta.
- **📝 Notițe** – notițe cu salvare automată și căutare.
- **🤖 Asistent AI** – chat cu un agent AI. Providerul, modelul și cheia API se aleg din Setări.
- **⚙️ Setări** – provider AI, model, API key (salvată criptat), system prompt, numele și mărimea
  roboțelului, „mereu deasupra”, pornire cu Windows, clipboard, temă.

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
├── renderer/          # HTML/CSS/JS pentru roboțel și panou
├── assets/            # buddy.svg, icon.svg, icon.png, icon.ico
└── scripts/make-ico.js# regenerează icon.ico din assets/icons/*.png
```
