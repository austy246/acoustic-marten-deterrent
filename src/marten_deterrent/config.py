"""Načítání a validace konfigurace (INI přes stdlib ``configparser``).

Žádné externí závislosti, funguje na Python 3.9+. Všechny klíče mají rozumný
default, takže config soubor je nepovinný.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from typing import Optional

SECTION = "marten"


@dataclass
class Config:
    """Kompletní runtime konfigurace plašiče."""

    # --- audio výstup ---
    audio_device: str = ""          # "" = výchozí ALSA zařízení; jinak jméno/index
    sample_rate: int = 44100

    # --- hlasitost a ochrana repro ---
    master_volume: float = 0.7      # 0–1
    peak_ceiling_dbfs: float = -3.0 # digitální rezerva, špičky pod touto hranicí
    fade_ms: float = 5.0            # fade in/out na okrajích každého prvku

    # --- časování / duty cycle ---
    min_gap_s: float = 8.0          # min. pauza mezi salvami
    max_gap_s: float = 45.0         # max. pauza mezi salvami

    # --- frekvenční obsah ---
    freq_min: float = 1000.0
    freq_max: float = 16000.0       # nad 16 kHz to akusticky nepřidá

    # --- startup sekvence ---
    startup_test_s: float = 8.0     # délka úvodní salvy na nastavení hlasitosti; 0 = vypnout

    # --- bezpečnost / běh ---
    max_runtime_hours: float = 12.0 # po této době nepřetržitého běhu -> auto off
    state_file: str = "/run/marten/state"

    # --- keepalive (volitelné) ---
    keepalive: bool = False
    keepalive_level_dbfs: float = -50.0

    def validate(self) -> None:
        """Zkontroluje smysluplnost hodnot, vyhodí ``ValueError`` při nesmyslu."""
        if self.sample_rate <= 0:
            raise ValueError("sample_rate musí být > 0")
        if not (0.0 <= self.master_volume <= 1.0):
            raise ValueError("master_volume musí být v rozsahu 0–1")
        if self.peak_ceiling_dbfs > 0:
            raise ValueError("peak_ceiling_dbfs musí být <= 0 (rezerva pod clip)")
        if self.fade_ms < 0:
            raise ValueError("fade_ms nesmí být záporné")
        if self.min_gap_s < 0 or self.max_gap_s < 0:
            raise ValueError("min_gap_s a max_gap_s nesmí být záporné")
        if self.max_gap_s < self.min_gap_s:
            raise ValueError("max_gap_s musí být >= min_gap_s")
        if self.freq_min <= 0:
            raise ValueError("freq_min musí být > 0")
        if self.freq_max <= self.freq_min:
            raise ValueError("freq_max musí být > freq_min")
        nyquist = self.sample_rate / 2.0
        if self.freq_max >= nyquist:
            # ořež na bezpečnou hodnotu pod Nyquistem
            self.freq_max = nyquist * 0.95
        if self.startup_test_s < 0:
            raise ValueError("startup_test_s nesmí být záporné")
        if self.max_runtime_hours <= 0:
            raise ValueError("max_runtime_hours musí být > 0")


def load_config(path: Optional[str] = None) -> Config:
    """Načte config z INI souboru. Když ``path`` je None nebo soubor chybí,
    vrátí defaulty.
    """
    cfg = Config()
    if not path:
        cfg.validate()
        return cfg

    parser = configparser.ConfigParser()
    read = parser.read(path, encoding="utf-8")
    if not read:
        raise FileNotFoundError(f"Config soubor nenalezen: {path}")

    if not parser.has_section(SECTION):
        # Toleruj i klíče v [DEFAULT] / kořenu — ale preferuj [marten].
        raise ValueError(f"Config musí obsahovat sekci [{SECTION}]")

    sec = parser[SECTION]

    def get_str(key: str, default: str) -> str:
        return sec.get(key, default).strip()

    def get_int(key: str, default: int) -> int:
        return sec.getint(key, default)

    def get_float(key: str, default: float) -> float:
        return sec.getfloat(key, default)

    def get_bool(key: str, default: bool) -> bool:
        return sec.getboolean(key, default)

    cfg = Config(
        audio_device=get_str("audio_device", cfg.audio_device),
        sample_rate=get_int("sample_rate", cfg.sample_rate),
        master_volume=get_float("master_volume", cfg.master_volume),
        peak_ceiling_dbfs=get_float("peak_ceiling_dbfs", cfg.peak_ceiling_dbfs),
        fade_ms=get_float("fade_ms", cfg.fade_ms),
        min_gap_s=get_float("min_gap_s", cfg.min_gap_s),
        max_gap_s=get_float("max_gap_s", cfg.max_gap_s),
        freq_min=get_float("freq_min", cfg.freq_min),
        freq_max=get_float("freq_max", cfg.freq_max),
        startup_test_s=get_float("startup_test_s", cfg.startup_test_s),
        max_runtime_hours=get_float("max_runtime_hours", cfg.max_runtime_hours),
        state_file=get_str("state_file", cfg.state_file),
        keepalive=get_bool("keepalive", cfg.keepalive),
        keepalive_level_dbfs=get_float("keepalive_level_dbfs", cfg.keepalive_level_dbfs),
    )
    cfg.validate()
    return cfg
