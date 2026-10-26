# Montaj: agent pentru editarea video-urilor

**Problema:** se pierd multe ore cu editarea video.
**Ce face Montaj:** primește regulile tale, eventual un video-exemplu, și materialul brut
(video, poze, muzică). Apoi lipește materialul într-un video prelucrat pentru social media,
ca draft sau ca video complet. Rezultatul se deschide în DaVinci Resolve sau CapCut, sau
direct în aplicație.

**Pentru:** oricine are nevoie să-și editeze video-uri pentru uz personal sau pentru social media.

## Cum lucrează (pașii din documentul de plan)

| # | Pas | Unde în cod |
|---|-----|-------------|
| 1 | **Input**: video, poze, fișiere audio (drag & drop) | `server.py` → upload |
| 2 | **ffmpeg / ffprobe ca „traducător”**: durată, rezoluție, fps, sunet, rotație | `engine/ff.py` |
| 3 | **Cadre**: 5 cadre pe video, fiecare cu momentul (timeframe-ul) lui | `engine/analyze.py` |
| 4 | **AI-ul nostru** (Claude Sonnet 5.5 prin API Anthropic): primește cadrele și măsurătorile și scrie planul de editare, pe care ffmpeg îl execută | `engine/agent.py`, `engine/plan.py` |
| 5 | **Validare**: planul e verificat pe fișierele reale și reparat → **Export** pentru CapCut / DaVinci Resolve | `engine/validate.py`, `engine/export.py` |
| 6 | **Randare** | `engine/render.py` |
| 7 | **Produsul** în formate acceptate: MP4, MP3, JPG, PNG (+ FCPXML, EDL, SRT) | `engine/render.py`, `engine/export.py` |

## Ce știe în plus

- **6 stiluri gata făcute**: TikTok/Reels, Vlog YouTube, Cinematic, Travel, Promo produs, Amintiri.
- **Video-exemplu**: marchează un clip ca *Exemplu*. Agentul măsoară ritmul tăieturilor
  (durata medie a unui cadru), luminozitatea și saturația, se uită la cadrele lui și copiază stilul.
- **Tăieturi pe ritm**: detectează BPM-ul și beat-urile melodiei și mută tăieturile pe beat.
- **Corecție automată de lumină și culoare** din statisticile reale ale imaginii
  (luminozitate, contrast, saturație), plus 8 look-uri: cinematic (teal & orange), cald, rece,
  vintage, alb-negru, viu, film cu granulație, mat.
- **Detectarea scenelor și a pauzelor**: taie din scenele naturale ale clipului, iar la
  clipurile cu voce scoate pauzele moarte.
- **Format vertical inteligent**: un clip orizontal pus într-un video 9:16 poate fi decupat
  sau așezat întreg peste o copie blurată a lui.
- **Mișcări de cameră** (Ken Burns pe poze, zoom, panoramare, punch-in) și **12 tranziții**.
- **Text pe ecran** în 5 stiluri (titlu, subtitrare, bandă jos, etichetă, cuvânt mare),
  cu diacritice românești, plus subtitrări arse în video.
- **Muzica se coboară automat** sub voce (ducking), iar sunetul e normalizat la -14 LUFS,
  nivelul folosit de TikTok, Instagram și YouTube.
- **Chat cu agentul**: „mai dinamic”, „scoate poza 3”, „culori mai calde”. Agentul reface
  planul și randează din nou.
- **Timeline editabil**: tragi clipurile ca să le reordonezi. Apeși pe un clip ca să-i schimbi
  tăierea, viteza, culoarea, mișcarea, tranziția și textele.
- **Versiunile anterioare** se păstrează (buton de undo).
- **Randare rapidă la modificări**: clipurile neschimbate sunt refolosite din cache.
- **Merge și fără AI**: butonul „Montaj automat” face un draft din reguli fixe (scene, pauze,
  beat-uri, culoare).

## Instalare (Windows)

1. Instalează **Python 3.10+** de pe python.org (bifează „Add Python to PATH”).
2. Instalează **ffmpeg**: deschide PowerShell și rulează `winget install Gyan.FFmpeg`.
3. Dublu-click pe **`Porneste-Montaj.bat`**. Se deschide browserul la http://127.0.0.1:8765
4. În aplicație: ⚙ **Setări** → pune cheia API Anthropic (de pe console.anthropic.com).
   Modelul implicit e **Claude Sonnet 5.5**; în Setări poți alege Opus 5.5 sau Haiku 5.5.

macOS / Linux: `./start.sh` (ffmpeg din `brew install ffmpeg` sau `sudo apt install ffmpeg`).

Cheia API rămâne doar pe calculatorul tău, în `montaj/workspace/settings.json`
(sau în variabila `ANTHROPIC_API_KEY`). Proiectele și fișierele stau în `montaj/workspace/`,
care nu intră în git.

## Exportul: ce primești

| Fișier | La ce folosește |
|--------|-----------------|
| `.mp4` | Video-ul final, H.264 + AAC, gata de postat (720p sau 1080p) |
| `.mp3` | Doar coloana sonoră |
| `_coperta.jpg` / `.png` | Coperta (thumbnail) cu titlul pe ea |
| `.fcpxml` | **DaVinci Resolve**: File → Import → Timeline. Vin tăieturile, tranzițiile, titlurile și muzica, legate de fișierele originale. Culoarea și viteza sunt scrise ca notă pe fiecare clip, ca să le refaci acolo. Merge și în Final Cut Pro. |
| `.edl` | Lista de tăieturi CMX3600: DaVinci, Premiere și majoritatea editoarelor |
| `.srt` | Textele și subtitrările. CapCut, YouTube și DaVinci pot importa SRT. |
| `_plan.json` | Planul complet de editare |

**CapCut** nu are un format public de import pentru proiecte. Pentru CapCut folosești
MP4-ul (gata editat) și, dacă vrei textele editabile, fișierul SRT.

## Cât costă un montaj cu AI

O cerere trimite ~5 cadre pe fiecare video, plus măsurătorile. Cu Sonnet 5.5, un montaj cu
10 clipuri costă de obicei câțiva cenți. Cadrele sunt puse în cache, așa că reviziile din
chat costă mai puțin.

## Teste

```
cd montaj
python -m pytest tests
```

Testele generează singure clipuri, poze și o melodie de probă. Apoi verifică analiza,
detectarea beat-urilor, randarea cu toate tranzițiile, look-urile și mișcările, exporturile
și forma exactă a cererii trimise la API (cu un server simulat).

## Fonturi

Inter (© The Inter Project Authors), sub licența SIL Open Font License 1.1, inclusă în `assets/fonts/OFL.txt`.
