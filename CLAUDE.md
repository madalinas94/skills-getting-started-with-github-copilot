# CLAUDE.md · Cutia Clasei

Instrucțiuni pentru Claude (și pentru oricine lucrează în proiect). Citește tot fișierul înainte să schimbi ceva.

## Ce e proiectul

**Cutia Clasei** este platforma internă a cursului de vibe coding. Are două spații:

| Spațiu | Cine vede | Ce conține |
| --- | --- | --- |
| 🔒 **Privat** (student ↔ trainer) | doar studentul care a trimis și trainerul | Întrebări, Teme & proiecte (fișiere, link GitHub, checklist, feedback) |
| 🌐 **Public** (toată clasa) | toți cei logați | Cutia de idei (propuneri trecute prin filtrul AI, voturi, „Aleasă”), Ghidul de vibe coding |

Interfața e în **română și engleză** (buton RO/EN) și are temă întunecată (implicit) și luminoasă.

## Minimul obligatoriu (din fișa trainerului): nu se strică niciodată

| Funcție | Regula | Unde e |
| --- | --- | --- |
| Pune o întrebare | O văd doar studentul care a pus-o și trainerul. | `GET/POST /api/questions` în `src/app.py` |
| Răspuns | Trainerul răspunde, studentul vede răspunsul. | `POST /api/questions/{id}/answer` |
| Scrie o propunere | Minimum: titlu, ce face aplicația, cine o folosește. | `ProposalIn` + `submit_proposal` |
| Modul AI | Retușează și cere detalii **doar unde lipsesc**, maxim 3 întrebări. | `src/ai.py` → `refine()` |
| Trimite propunerea | Studentul **aprobă** varianta finală înainte să o trimită (`approved: true`, verificat pe server). | `submit_proposal` |
| Trainerul alege | Vede toate propunerile și le marchează „Aleasă”. | `POST /api/proposals/{id}/choose` |

Ce verifică AI-ul la fiecare propunere: **problema** (ce rezolvă și pentru cine), **funcțiile** (cele 3 lucruri sigure), **datele** (de unde vin), **mărimea** (se face într-o oră? dacă nu, ce parte întâi). AI-ul nu decide în locul studentului: arată ce a înțeles, spune ce lipsește, studentul alege ce trimite.

## Reguli de securitate: obligatorii

1. **Cheia API nu ajunge niciodată în browser sau pe GitHub.** Apelurile către Claude se fac doar din `src/ai.py`, pe server. Cheia stă în variabila de mediu `ANTHROPIC_API_KEY` sau în `.env` (ignorat de git). Nu scrie chei în cod, în teste, în README sau în mesaje de commit.
2. **Ai urcat o cheie din greșeală?** Spune-i imediat utilizatorului s-o regenereze din consola Anthropic. Ștearsă din cod, rămâne în istoricul git.
3. **Accesul se verifică pe server, nu doar în interfață.** Fiecare endpoint nou folosește `current_user` / `require_student` / `require_trainer` și filtrează după `author_key`. Ascunderea unui buton nu e protecție.
4. **Testează cu două conturi.** Orice funcție privată are un test în care studentul B **nu** vede datele studentului A (vezi `tests/test_app.py`).
5. **Fișierele încărcate** se salvează cu nume aleatorii în `data/uploads/`, se descarcă doar prin API (după verificarea accesului), mereu ca `attachment` + `application/octet-stream` + `nosniff`. Limite: 5 fișiere, 10 MB, extensii din `ALLOWED_EXTENSIONS`.
6. **Linkurile** trimise de utilizatori se acceptă doar dacă încep cu `http://` sau `https://` (fără `javascript:`), verificat pe server și în interfață.
7. **Fără `innerHTML` cu text de la utilizatori sau de la AI.** În `app.js` totul se construiește cu `el(...)` și noduri text; markdown-ul AI trece prin `renderMd()`, care nu folosește HTML.
8. Parolele se salvează doar ca hash PBKDF2 cu salt; codul de trainer vine din `TRAINER_CODE`.

## Reguli pentru AI

- Modelul implicit: `claude-opus-5-5` (`CUTIA_MODEL`). Răspunsurile vin în limba interfeței (antetul `X-Lang`).
- Propuneri: răspuns structurat (JSON schema), maxim 3 întrebări, nu inventează funcții, câmpurile goale rămân goale. Fără cheie → `refine_local()` (retușare simplă, aceleași câmpuri).
- **Nimic nu se trimite fără acordul studentului**: AI-ul doar propune; trimiterea cere checkbox-ul de aprobare, iar orice editare cere o nouă aprobare.
- Răspunsul rapid la întrebări (`answer_question`) e marcat mereu „AI · neverificat de trainer”. Răspunsul trainerului rămâne cel **oficial** și apare primul. Se generează o singură dată per întrebare.
- Dacă AI-ul nu e disponibil, aplicația merge în continuare (mod local / sfaturi din ghid). Nu bloca nicio funcție obligatorie pe AI.

## Structura

```
src/app.py            API FastAPI: login, întrebări, teme & proiecte, propuneri, limbă (X-Lang)
src/ai.py             Modulul AI: retușarea propunerilor + tutorul pentru întrebări
src/static/index.html Scheletul platformei (sidebar privat/public, 5 ecrane)
src/static/i18n.js    TOATE textele RO + EN și ghidul de vibe coding (15 topicuri)
src/static/app.js     Logica interfeței (fără framework)
src/static/styles.css Design: tokens pe :root, dark/light, mobil, reduced motion
tests/test_app.py     Teste API (acces, AI, upload, limbi)
data/                 Date + fișiere încărcate (ignorat de git)
```

## Comenzi

```bash
pip install -r requirements.txt
cp .env.example .env              # pune cheia API aici, dacă ai una
uvicorn src.app:app --reload      # http://localhost:8000
pytest                            # rulează după fiecare schimbare
```

## Convenții

- **Fiecare text din interfață există în română ȘI în engleză** în `src/static/i18n.js` (`STRINGS.ro` / `STRINGS.en`, aceleași chei). Mesajele de eroare ale serverului sunt în `MESSAGES` din `app.py`, tot în ambele limbi.
- Topicurile din ghid au aceleași chei în `TOPICS` (`i18n.js`) și `TOPICS` (`app.py`). Când adaugi un topic, îl adaugi în ambele, în ambele limbi.
- Comentariile din cod sunt în română, scurte, și explică *de ce*.
- Design: culorile doar din variabilele CSS de pe `:root` (tema dark e implicită, light prin `data-theme="light"`). Verifică orice ecran nou pe telefon (390px), în ambele teme, și cu `prefers-reduced-motion`.
- Interfața marchează clar spațiul: `🔒 Privat` sau `🌐 Public`. Un ecran nou trebuie să spună în ce spațiu e.
- Fără dependențe noi în frontend (fără build). În backend, doar ce e în `requirements.txt`.

## Când adaugi o funcție

1. Endpoint cu verificare de acces pe server + test cu două conturi.
2. Texte în `i18n.js` în ambele limbi (+ mesaje de eroare în `MESSAGES`).
3. Verifică: desktop + mobil, dark + light, RO + EN.
4. `pytest` trece. Actualizează README-ul (funcții în plus) și, dacă e cazul, acest fișier.
5. Commit mic, cu mesaj clar. Niciodată `.env`, `data/` sau chei.

## Gata când (checklist-ul temei)

- [ ] Toate funcțiile din minimul obligatoriu merg.
- [ ] O întrebare nu apare la alt student.
- [ ] Modulul AI cere detalii doar când lipsește ceva și nu trimite nimic fără acordul studentului.
- [ ] Codul e pe GitHub, cu README.
- [ ] Nicio cheie API în cod sau în istoricul repo-ului.
- [ ] Trainerul are acces la repo și a primit linkul.
