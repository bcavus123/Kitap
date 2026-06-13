"""Matplotlib ile grafik/görsel üretimi (Spec Bölüm 16 adım 37, Bölüm 9.2).

KDP için minimum 300 DPI PNG üretir. Başsız (headless) ortam için Agg backend.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # GUI yok; CI/worker'da güvenli
import matplotlib.pyplot as plt  # noqa: E402

KDP_MIN_DPI = 300


def generate_bar_chart(
    title: str, labels: list[str], values: list[float], dpi: int = KDP_MIN_DPI
) -> bytes:
    """Etiket/değer çiftlerinden PNG (≥300 DPI) bar grafik üretir."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, values)
    ax.set_title(title)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=max(dpi, KDP_MIN_DPI))
    plt.close(fig)
    return buffer.getvalue()


def generate_line_chart(
    title: str, x: list[float], y: list[float], dpi: int = KDP_MIN_DPI
) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y)
    ax.set_title(title)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=max(dpi, KDP_MIN_DPI))
    plt.close(fig)
    return buffer.getvalue()
