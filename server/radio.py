"""Radio station configuration and lookup.

KFO-Server owners can drop a ``config/radio.json`` file listing named radio
stream URLs. Players can then use ``/radio`` to list them and ``/radio <id>``
to play one anywhere, without the usual DJ/area music restrictions. The URLs
are operator-controlled, so ``/radio`` acts as a safe shortcut to ``/play``.
"""

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("radio")


@dataclass
class RadioStation:
    """A single configured radio station."""

    id: int
    name: str
    url: str

    def __post_init__(self):
        """Validate the station after construction."""
        self.id = int(self.id)
        if self.id < 1:
            raise ValueError(f"Radio station id must be a positive integer, got {self.id!r}.")

        self.name = str(self.name).strip()
        if not self.name:
            raise ValueError("Radio station name must not be empty.")

        self.url = str(self.url).strip()
        if not (self.url.startswith("http://") or self.url.startswith("https://")):
            raise ValueError(f"Radio station url must start with http:// or https://, got {self.url!r}.")


class RadioManager:
    """Loads, validates and looks up the configured radio stations."""

    DEFAULT_PATH = "config/radio.json"

    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        self._stations = []

    @property
    def stations(self):
        """Return a copy of the configured stations."""
        return list(self._stations)

    def reload(self):
        """(Re)load stations from the JSON file, clearing the list on failure."""
        stations = []
        if os.path.isfile(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    raw = json.load(handle)
                if not isinstance(raw, list):
                    raise ValueError(f"{self.path} must contain a JSON array of radio objects.")
                for entry in raw:
                    stations.append(RadioStation(**entry))
            except (OSError, ValueError) as exc:
                logger.debug("Cannot load radio stations from %s: %s", self.path, exc)
        self._stations = stations

    def find(self, radio_id):
        """Return the station with the given id, or ``None`` if not found."""
        try:
            radio_id = int(radio_id)
        except (TypeError, ValueError):
            return None
        for station in self._stations:
            if station.id == radio_id:
                return station
        return None

    def list_text(self):
        """Format the station list as ``id > name`` lines for chat."""
        if not self._stations:
            return "No radio stations are configured."
        return "\n".join(f"{station.id} > {station.name}" for station in self._stations)
