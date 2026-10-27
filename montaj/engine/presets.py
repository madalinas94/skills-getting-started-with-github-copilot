"""Editing styles offered in the UI. Used by both the automatic planner and the AI prompt."""

PRESETS = {
    "reels": {
        "captions": "karaoke", "beat_fx": "mix", "beat_every": 2, "animations": ["pop", "slide_up"],
        "label": "TikTok / Reels dinamic",
        "aspect": "9:16", "duration": 30, "pace": 1.8,
        "transitions": ["cut", "cut", "zoomin", "cut", "smoothleft", "cut"],
        "look": "vivid", "fit": "fill", "keep_audio": False,
        "motions": ["punch_in", "none", "zoom_in", "none"],
        "brief": "Hook puternic în primele 2 secunde, tăieturi rapide pe ritm, text scurt pe ecran, energie mare.",
    },
    "vlog": {
        "captions": "clean", "beat_fx": "none", "beat_every": 4, "animations": ["slide_up", "fade"],
        "label": "Vlog YouTube",
        "aspect": "16:9", "duration": 60, "pace": 4.0,
        "transitions": ["cut", "cut", "cut", "dissolve"],
        "look": "warm", "fit": "blur_bg", "keep_audio": True,
        "motions": ["none"],
        "brief": "Povestea cronologică, păstrează vorbitul, scoate pauzele moarte, subtitrări, muzică încet pe fundal.",
    },
    "cinematic": {
        "captions": "clean", "beat_fx": "none", "beat_every": 4, "animations": ["zoom_out", "fade"],
        "label": "Cinematic",
        "aspect": "16:9", "duration": 45, "pace": 3.4,
        "transitions": ["dissolve", "cut", "fadeblack", "dissolve"],
        "look": "cinematic", "fit": "fill", "keep_audio": False, "vignette": True,
        "motions": ["zoom_in", "pan_right", "none", "zoom_out"],
        "brief": "Ritm calm, cadre largi, mișcări lente, grade teal & orange, titlu elegant, final cu fade la negru.",
    },
    "travel": {
        "captions": "bold", "beat_fx": "zoom", "beat_every": 2, "animations": ["slide_up", "pop"],
        "label": "Travel montage",
        "aspect": "9:16", "duration": 30, "pace": 2.2,
        "transitions": ["cut", "smoothleft", "cut", "zoomin", "wipeleft"],
        "look": "warm", "fit": "fill", "keep_audio": False,
        "motions": ["zoom_in", "pan_left", "none", "pan_right"],
        "brief": "Locuri, oameni, detalii; alternează cadre largi cu detalii, numele locului ca etichetă.",
    },
    "promo": {
        "captions": "bold", "beat_fx": "flash", "beat_every": 1, "animations": ["pop", "zoom_out"],
        "label": "Promo produs / afacere",
        "aspect": "9:16", "duration": 20, "pace": 1.5,
        "transitions": ["cut", "cut", "zoomin", "cut"],
        "look": "vivid", "fit": "fill", "keep_audio": False,
        "motions": ["punch_in", "zoom_in", "none"],
        "brief": "Problemă → produs → beneficii → call to action; cuvinte mari pe ecran, foarte rapid.",
    },
    "memories": {
        "captions": "clean", "beat_fx": "none", "beat_every": 4, "animations": ["typewriter", "fade"],
        "label": "Amintiri / aniversare",
        "aspect": "16:9", "duration": 60, "pace": 3.2,
        "transitions": ["dissolve", "fade", "dissolve", "fadewhite"],
        "look": "film", "fit": "blur_bg", "keep_audio": False,
        "motions": ["zoom_in", "pan_right", "zoom_out", "pan_left"],
        "brief": "Emoționant, cronologic, Ken Burns pe poze, tranziții moi, titlu la început și mesaj la final.",
    },
}

DEFAULT = "reels"


def get(name: str) -> dict:
    return PRESETS.get(name) or PRESETS[DEFAULT]
