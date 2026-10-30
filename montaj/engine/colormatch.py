"""Match the look of a reference image (a film still, a creator you like) and save it as a
3D LUT (.cube) that the renderer applies and DaVinci Resolve can load."""

from pathlib import Path

import numpy as np
from PIL import Image

LUT_SIZE = 33


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _lab_to_srgb(lab: np.ndarray) -> np.ndarray:
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    c = xyz @ m.T
    rgb = np.where(c > 0.0031308, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055, 12.92 * c)
    return np.clip(rgb, 0, 1)


def _stats(img: Image.Image):
    a = np.asarray(img.convert("RGB").resize((256, int(256 * img.height / img.width) or 1))).reshape(-1, 3) / 255.0
    lab = _srgb_to_lab(a)
    return lab.mean(0), lab.std(0) + 1e-6


def make_lut(reference: Image.Image, footage: list, strength: float = 0.8):
    """LUT that moves the footage's colour statistics towards the reference's (Reinhard
    transfer in Lab), softened by strength so skin tones stay believable."""
    mu_r, sd_r = _stats(reference)
    stats = [_stats(f) for f in footage] or [(mu_r, sd_r)]
    mu_s = np.mean([s[0] for s in stats], 0)
    sd_s = np.mean([s[1] for s in stats], 0)
    ratio = np.clip(sd_r / sd_s, 0.6, 1.6)  # never crush or blow out contrast completely
    g = np.linspace(0, 1, LUT_SIZE)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")  # .cube order: red changes fastest
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    lab = _srgb_to_lab(rgb)
    moved = (lab - mu_s) * ratio + mu_r
    out = _lab_to_srgb(moved)
    return rgb * (1 - strength) + out * strength


def write_cube(table: np.ndarray, dest: Path, title: str = "Montaj look"):
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {LUT_SIZE}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in table]
    dest.write_text("\n".join(lines) + "\n", encoding="ascii")
    return dest
