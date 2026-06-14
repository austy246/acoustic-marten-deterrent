"""Hlavní běhová smyčka — spojuje engine, stavový soubor a bezpečnostní timeout.

Importuje ``sounddevice`` líně (až při spuštění), aby šly ostatní části (config,
``--list-devices`` chyby, importy) používat i tam, kde PortAudio chybí.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from typing import Optional

import numpy as np

from .config import Config
from .control import StateController
from .engine import SoundEngine

log = logging.getLogger("marten")


class Runner:
    """Orchestruje přehrávání: startup sekvence, náhodné salvy, pauzy, timeout."""

    def __init__(self, cfg: Config, engine: Optional[SoundEngine] = None) -> None:
        self.cfg = cfg
        self.engine = engine or SoundEngine(cfg)
        self.control = StateController(cfg.state_file)
        self._stop = threading.Event()
        self._sd = None  # líně importovaný modul sounddevice

    # ----- sounddevice -----

    def _ensure_sd(self):
        if self._sd is None:
            import sounddevice as sd  # lazy import
            self._sd = sd
        return self._sd

    # ----- signály -----

    def install_signal_handlers(self) -> None:
        # signal.signal funguje jen v hlavním vlákně; v jiném (testy) to tiše
        # přeskočíme — čisté ukončení pak řeší přímo _stop event.
        try:
            signal.signal(signal.SIGTERM, self._on_signal)
            signal.signal(signal.SIGINT, self._on_signal)
        except ValueError:
            log.debug("Signal handlery nelze nainstalovat (ne hlavní vlákno).")

    def _on_signal(self, signum, _frame) -> None:  # noqa: ANN001
        log.info("Přijat signál %s — ukončuji a zastavuji přehrávání.", signum)
        self._stop.set()
        if self._sd is not None:
            try:
                self._sd.stop()
            except Exception:  # pragma: no cover - best effort
                pass

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    # ----- přehrávání -----

    def _play(self, sig: np.ndarray) -> None:
        if self._stop.is_set() or sig.size == 0:
            return
        sd = self._ensure_sd()
        sd.play(sig, self.cfg.sample_rate, device=self.engine.device)
        sd.wait()

    def _play_burst(self) -> None:
        """Jeden plašicí prvek s náhodným skokem hlasitosti."""
        elem = self.engine.random_element()
        self._play(self.engine.apply_gain(elem, jitter=True))

    def _interruptible_sleep(self, dur: float) -> None:
        """Pauza po malých krocích, ať se dá rychle reagovat na stop/stav.

        Při ``keepalive`` hraje během pauzy velmi tichý tón v krátkých blocích.
        """
        step = 0.25
        elapsed = 0.0
        while elapsed < dur and not self._stop.is_set():
            chunk = min(step, dur - elapsed)
            if self.cfg.keepalive:
                self._play(self.engine.keepalive_tone(chunk))
            else:
                self._stop.wait(chunk)
            elapsed += chunk

    def _gap(self) -> None:
        dur = self.engine.rng.uniform(self.cfg.min_gap_s, self.cfg.max_gap_s)
        log.debug("Pauza %.1f s.", dur)
        self._interruptible_sleep(dur)

    # ----- veřejné režimy -----

    def run_once(self, n_elements: int = 5) -> None:
        """Přehraje pár různých prvků a skončí (``--once`` / ``--test``)."""
        self.install_signal_handlers()
        log.info("Testovací režim: přehrávám %d prvků.", n_elements)
        for i in range(n_elements):
            if self._stop.is_set():
                break
            log.info("Prvek %d/%d.", i + 1, n_elements)
            self._play_burst()
            if i < n_elements - 1:
                self._interruptible_sleep(self.engine.rng.uniform(0.3, 1.0))
        log.info("Hotovo.")

    def _startup_sequence(self) -> None:
        """Oznámí start a přehraje úvodní salvu na nastavení hlasitosti."""
        if self.cfg.startup_test_s <= 0:
            log.info("Začínám plašit (úvodní salva vypnutá, startup_test_s=0).")
            return
        log.info(
            "Začínám plašit. Úvodní testovací salva (~%.0f s) pro nastavení "
            "hlasitosti — dolaď alsamixer / master_volume.",
            self.cfg.startup_test_s,
        )
        end = time.monotonic() + self.cfg.startup_test_s
        while time.monotonic() < end and not self._stop.is_set():
            self._play_burst()
        log.info("Úvodní salva hotová, přecházím do normálního provozu "
                 "(náhodné intervaly).")

    def run(self) -> None:
        """Hlavní nepřetržitý režim (systemd / ruční dlouhý běh)."""
        self.install_signal_handlers()
        self.control.ensure_dir()

        self._startup_sequence()

        runtime_limit = self.cfg.max_runtime_hours * 3600.0
        start = time.monotonic()
        timed_out = False
        was_on = True

        while not self._stop.is_set():
            # Bezpečnostní timeout: po max_runtime_hours se sám přepne do off.
            if not timed_out and (time.monotonic() - start) >= runtime_limit:
                log.warning(
                    "Dosažen bezpečnostní limit %.1f h — přepínám do OFF. "
                    "Pro nahození zapiš 'on' do %s nebo restartuj službu.",
                    self.cfg.max_runtime_hours, self.cfg.state_file,
                )
                self.control.set_off()
                timed_out = True

            on = self.control.is_on()

            if not on:
                if was_on:
                    log.info("Stav OFF — ztišuji (čekám na 'on').")
                    was_on = False
                self._interruptible_sleep(1.0)
                continue

            if not was_on:
                log.info("Stav ON — pokračuji v plašení.")
                was_on = True
                if timed_out:
                    # Ruční nahození po timeoutu = nový odpočet limitu.
                    start = time.monotonic()
                    timed_out = False

            self._play_burst()
            self._gap()

        log.info("Smyčka ukončena.")
