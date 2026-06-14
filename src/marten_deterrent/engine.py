"""Zvukový engine — procedurální generování plašicích prvků.

Žádné audio soubory; vše se počítá z numpy. Prvky se náhodně střídají, mají
náhodnou frekvenci, délku i hlasitost (proti habituaci a pro efekt leknutí).
Každý prvek je normalizovaný na špičku 1.0 a teprve runner mu přiřadí finální
gain pod ``peak_ceiling_dbfs`` — tím je zaručena digitální rezerva.
"""

from __future__ import annotations

import random
from typing import List, Optional, Union

import numpy as np

from .config import Config

# Interní rozsah náhodných skoků hlasitosti mezi salvami (efekt leknutí).
# Násobí se přes master_volume, takže nikdy nepřekročí strop.
_VOLUME_JITTER_MIN = 0.45
_VOLUME_JITTER_MAX = 1.0

ElementName = str


def _dbfs_to_lin(dbfs: float) -> float:
    return float(10.0 ** (dbfs / 20.0))


def _resolve_device(audio_device: str) -> Optional[Union[int, str]]:
    """Prázdný řetězec -> None (výchozí zařízení). Číslo -> index. Jinak jméno."""
    if not audio_device:
        return None
    try:
        return int(audio_device)
    except ValueError:
        return audio_device


class SoundEngine:
    """Generátor plašicích zvukových prvků."""

    ELEMENTS: List[ElementName] = ["chirp", "trill", "noise", "tone"]

    def __init__(self, cfg: Config, rng: Optional[random.Random] = None) -> None:
        self.cfg = cfg
        self.sr = cfg.sample_rate
        self.rng = rng or random.Random()
        self.device = _resolve_device(cfg.audio_device)
        self._ceiling_lin = _dbfs_to_lin(cfg.peak_ceiling_dbfs)

    # ----- pomocné -----

    def _rand_freq(self) -> float:
        return self.rng.uniform(self.cfg.freq_min, self.cfg.freq_max)

    def _clamp_freq(self, f: float) -> float:
        return float(min(max(f, self.cfg.freq_min), self.cfg.freq_max))

    def _t(self, n: int) -> np.ndarray:
        return np.arange(n, dtype=np.float64) / self.sr

    @staticmethod
    def _normalize(sig: np.ndarray) -> np.ndarray:
        peak = float(np.max(np.abs(sig))) if sig.size else 0.0
        if peak > 0:
            sig = sig / peak
        return sig

    def _apply_fade(self, sig: np.ndarray) -> np.ndarray:
        nf = int(self.cfg.fade_ms / 1000.0 * self.sr)
        if nf > 0 and sig.size > 2 * nf:
            ramp = np.linspace(0.0, 1.0, nf, dtype=np.float64)
            sig[:nf] *= ramp
            sig[-nf:] *= ramp[::-1]
        return sig

    # ----- jednotlivé prvky (vrací normalizovaný signál, peak ~1.0) -----

    def chirp(self, dur: float, f0: float, f1: float) -> np.ndarray:
        """Exponenciální sweep z f0 do f1 (rostoucí i klesající)."""
        n = max(1, int(dur * self.sr))
        t = self._t(n)
        f0 = max(self._clamp_freq(f0), 1.0)
        f1 = max(self._clamp_freq(f1), 1.0)
        if abs(f1 - f0) < 1.0:
            phase = 2.0 * np.pi * f0 * t
        else:
            k = (f1 / f0) ** (1.0 / dur)
            phase = 2.0 * np.pi * f0 * ((k ** t - 1.0) / np.log(k))
        return np.sin(phase)

    def trill(self, dur: float, f1: float, f2: float, rate: float) -> np.ndarray:
        """Trylek — rychlé střídání dvou tónů (``rate`` přepnutí za sekundu)."""
        n = max(1, int(dur * self.sr))
        t = self._t(n)
        f1 = self._clamp_freq(f1)
        f2 = self._clamp_freq(f2)
        sel = (np.floor(t * rate).astype(np.int64) % 2) == 0
        return np.where(sel, np.sin(2 * np.pi * f1 * t), np.sin(2 * np.pi * f2 * t))

    def noise(self, dur: float, flo: float, fhi: float) -> np.ndarray:
        """Pásmově omezená šumová salva (FFT maskou)."""
        n = max(2, int(dur * self.sr))
        flo = self._clamp_freq(flo)
        fhi = self._clamp_freq(fhi)
        if fhi < flo:
            flo, fhi = fhi, flo
        white = np.asarray([self.rng.uniform(-1.0, 1.0) for _ in range(n)])
        spec = np.fft.rfft(white)
        freqs = np.fft.rfftfreq(n, d=1.0 / self.sr)
        mask = (freqs >= flo) & (freqs <= fhi)
        spec[~mask] = 0.0
        out = np.fft.irfft(spec, n)
        return out

    def tone(self, dur: float, f: float) -> np.ndarray:
        """Čistý tón."""
        n = max(1, int(dur * self.sr))
        t = self._t(n)
        return np.sin(2 * np.pi * self._clamp_freq(f) * t)

    # ----- náhodný prvek -----

    def random_element(self) -> np.ndarray:
        """Vygeneruje náhodný prvek (normalizovaný, s fade in/out)."""
        kind = self.rng.choice(self.ELEMENTS)
        if kind == "chirp":
            dur = self.rng.uniform(0.4, 1.6)
            f0 = self._rand_freq()
            f1 = self._rand_freq()
            sig = self.chirp(dur, f0, f1)
        elif kind == "trill":
            dur = self.rng.uniform(0.5, 1.8)
            f1 = self._rand_freq()
            f2 = self._rand_freq()
            rate = self.rng.uniform(8.0, 25.0)
            sig = self.trill(dur, f1, f2, rate)
        elif kind == "noise":
            dur = self.rng.uniform(0.3, 1.2)
            center = self._rand_freq()
            bw = self.rng.uniform(800.0, 4000.0)
            sig = self.noise(dur, center - bw / 2.0, center + bw / 2.0)
        else:  # tone
            dur = self.rng.uniform(0.3, 1.2)
            f = self._rand_freq()
            sig = self.tone(dur, f)

        sig = self._normalize(sig)
        sig = self._apply_fade(sig)
        return sig.astype(np.float32)

    def apply_gain(self, sig: np.ndarray, jitter: bool = True) -> np.ndarray:
        """Přiřadí finální hlasitost pod stropem. Vstup je normalizovaný na 1.0.

        Výsledná špička = ceiling_lin * master_volume * factor, tedy vždy
        <= ceiling_lin (digitální rezerva je zaručena).
        """
        factor = 1.0
        if jitter:
            factor = self.rng.uniform(_VOLUME_JITTER_MIN, _VOLUME_JITTER_MAX)
        amp = self._ceiling_lin * self.cfg.master_volume * factor
        return (sig * amp).astype(np.float32)

    def keepalive_tone(self, dur: float) -> np.ndarray:
        """Velmi tichý tón pro udržení aktivních repro mimo auto-standby."""
        n = max(1, int(dur * self.sr))
        t = self._t(n)
        f = (self.cfg.freq_min + self.cfg.freq_max) / 2.0
        sig = np.sin(2 * np.pi * self._clamp_freq(f) * t)
        sig = self._apply_fade(sig)
        amp = _dbfs_to_lin(self.cfg.keepalive_level_dbfs)
        return (sig * amp).astype(np.float32)
