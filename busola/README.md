# Busola: cariera ta, cu nordul arătat

Aplicație personală de căutare și aplicare la joburi, în română și engleză, construită ca un singur fișier HTML (`index.html`).

## Ce face

- **Radar**: joburi reale din România și din străinătate, cu scor de potrivire față de profil, filtre pe regiune, domeniu și companii mari.
- **Carieră**: trasee de carieră („Rolul ideal”) și un plan de creștere cu skill-uri, certificări, MBA, cursuri, bootcamp-uri, conferințe și evenimente, plus căutarea „Întreabă Busola”.
- **Rețea**: companii de vis urmărite zilnic, contacte (foști colegi, alumni) și mesaje de cerere de recomandare; postări publice „we're hiring”.
- **Aplicări**: tablou cu etapele aplicărilor și follow-up-uri.
- **Atelier**: CV și scrisoare de intenție personalizate pe job, antrenor de interviu, dosar de companie și control de calitate al CV-ului (ATS + scanare de formulări care sună generat).
- **Profil**: încărcare CV (PDF/DOCX), preferințe, optimizare LinkedIn.

## Cum rulează

Aplicația e făcută pentru a rula ca Artifact pe claude.ai, unde primește:

- o bază de date privată (doar proprietarul o poate citi),
- funcțiile de AI (`window.claude`), folosite pentru CV-uri, scrisori, mesaje și analize,
- descărcarea fișierelor.

Deschisă direct în browser (sau pe GitHub Pages), interfața funcționează și salvează datele local, în `localStorage`, dar funcțiile de AI nu sunt disponibile.

Datele personale (CV, joburi, aplicări, contacte) **nu** sunt în acest repository: stau în baza de date privată a aplicației.

## Capturi

![Rețea, desktop](screenshots/retea-desktop.png)
![Network, mobile](screenshots/network-mobile-en.png)
