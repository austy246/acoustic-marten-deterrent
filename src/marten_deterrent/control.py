"""Runtime ovládání přes stavový soubor (on/off).

Stavový soubor umožní ztlumit/nahodit plašič bez restartu procesu — kontroluje
se v každé iteraci smyčky. Když soubor neexistuje, bere se to jako ``on`` (po
spuštění zařízení rovnou plaší).
"""

from __future__ import annotations

import os
from typing import Optional


class StateController:
    """Čte a zapisuje stav ``on``/``off`` ze/do souboru."""

    def __init__(self, state_file: str) -> None:
        self.state_file = state_file

    def ensure_dir(self) -> None:
        """Pokusí se vytvořit nadřazený adresář (např. /run/marten).

        Selhání tiše ignoruje — na PC při testu nemusí být zapisovatelný a
        výchozí chování (chybějící soubor = on) stejně funguje.
        """
        parent = os.path.dirname(self.state_file)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError:
                pass

    def read(self) -> Optional[str]:
        """Vrátí ``"on"``/``"off"``, nebo None když soubor chybí/nejde přečíst."""
        try:
            with open(self.state_file, "r", encoding="utf-8") as fh:
                val = fh.read().strip().lower()
        except OSError:
            return None
        if val in ("on", "off"):
            return val
        # Neznámý obsah bereme konzervativně jako off, ať nehrajeme omylem.
        return "off" if val else None

    def is_on(self) -> bool:
        """True = hrát. Chybějící soubor znamená on (default po startu)."""
        state = self.read()
        if state is None:
            return True
        return state == "on"

    def set_off(self) -> bool:
        """Zapíše ``off`` (používá bezpečnostní timeout). Vrací úspěch zápisu."""
        return self._write("off")

    def set_on(self) -> bool:
        return self._write("on")

    def _write(self, value: str) -> bool:
        self.ensure_dir()
        try:
            with open(self.state_file, "w", encoding="utf-8") as fh:
                fh.write(value + "\n")
            return True
        except OSError:
            return False
