# Cutia Clasei

Aplicație în care studenții pun întrebări trainerului și propun proiecte pentru ora următoare.

## Funcții

**Obligatorii**

| Funcție | Cum e implementată |
| --- | --- |
| Pune o întrebare | Studentul scrie întrebarea; o văd doar el și trainerul. |
| Răspuns | Trainerul răspunde (sau editează răspunsul); studentul îl vede sub întrebare. |
| Scrie o propunere | Titlu, ce face aplicația, cine o folosește. |
| Modul AI | Claude retușează textul și cere detalii **doar** pentru câmpurile care lipsesc sau sunt vagi. |
| Trimite propunerea | Studentul editează și aprobă varianta finală (checkbox) înainte de trimitere; orice editare cere o nouă aprobare. |
| Trainerul alege | Trainerul vede toate propunerile și le marchează „Aleasă”. |

**În plus:** întrebări anonime (trainerul vede „Anonim”), categorii, voturi pe propuneri, căutare și filtre, sortare după voturi / alese, badge cu întrebările fără răspuns, reîmprospătare automată, temă dark, layout pentru telefon.

## Pornire

```bash
pip install -r requirements.txt
uvicorn src.app:app --reload
```

Deschide http://localhost:8000. Studentul intră cu numele; trainerul cu numele și codul de trainer.

### Configurare (variabile de mediu)

| Variabilă | Implicit | Rol |
| --- | --- | --- |
| `TRAINER_CODE` | `trainer` | Codul cerut la autentificarea trainerului. Schimbă-l! |
| `ANTHROPIC_API_KEY` | – | Activează modulul AI cu Claude. Fără cheie se folosește o retușare locală simplă. |
| `CUTIA_AI` | `auto` | `auto` / `on` / `off` |
| `CUTIA_MODEL` | `claude-opus-5-5` | Modelul Claude folosit. |
| `CUTIA_DATA` | `data/cutia.json` | Unde se salvează întrebările și propunerile. |

## API

| Metodă | Endpoint | Cine |
| --- | --- | --- |
| POST | `/api/login` | toți |
| GET | `/api/questions` | trainerul vede tot, studentul doar întrebările lui |
| POST | `/api/questions` | student |
| POST | `/api/questions/{id}/answer` | trainer |
| POST | `/api/proposals/refine` | student (modul AI) |
| GET | `/api/proposals` | toți |
| POST | `/api/proposals` | student (cere `approved: true`) |
| POST | `/api/proposals/{id}/vote` | student |
| POST | `/api/proposals/{id}/choose` | trainer |

## Teste

```bash
pytest
```
