"""Utility for assigning anonymous display names to students."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import random
from threading import Lock

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "celebrity_names.txt"
# Fallback names in case the text file is missing for some reason.
_FALLBACK_NAMES = [
    "Ross Geller",
    "Rachel Green",
    "Chandler Bing",
    "Monica Geller",
    "Joey Tribbiani",
    "Phoebe Buffay",
    "Gunther",
    "Janice Litman",
    "Carol Willick",
    "Lorelai Gilmore",
    "Rory Gilmore",
    "Luke Danes",
    "Emily Gilmore",
    "Richard Gilmore",
    "Paris Geller",
    "Jay Pritchett",
    "Gloria Delgado-Pritchett",
    "Claire Dunphy",
    "Phil Dunphy",
    "Mitchell Pritchett",
    "Cameron Tucker",
    "Haley Dunphy",
    "Alex Dunphy",
    "Luke Dunphy",
    "Manny Delgado",
    "Sheldon Cooper",
    "Leonard Hofstadter",
    "Penny",
    "Howard Wolowitz",
    "Rajesh Koothrappali",
    "Amy Farrah Fowler",
    "Bernadette Rostenkowski-Wolowitz",
    "Michael Scott",
    "Dwight Schrute",
    "Jim Halpert",
    "Pam Beesly",
    "Leslie Knope",
    "Ron Swanson",
    "April Ludgate",
]


class NameAssigner:
    """Provides randomized, non-repeating aliases sourced from a text file."""

    def __init__(self, names: list[str]):
        cleaned = [name.strip() for name in names if name.strip()]
        if not cleaned:
            raise ValueError("Name list cannot be empty.")
        self._names = cleaned
        self._pool: deque[str] = deque()
        self._lock = Lock()
        self._rng = random.Random()
        self._refill_pool()

    @classmethod
    def from_default_file(cls) -> "NameAssigner":
        names = _fallback_names()
        if _DATA_PATH.exists():
            try:
                names = _DATA_PATH.read_text(encoding="utf-8").splitlines()
            except OSError:
                names = _fallback_names()
        return cls(names)

    def next_name(self) -> str:
        with self._lock:
            if not self._pool:
                self._refill_pool()
            return self._pool.popleft()

    def reset_cycle(self) -> None:
        """Clear the remaining pool and reshuffle all names for a fresh cycle."""
        with self._lock:
            self._pool.clear()
            self._refill_pool()

    def _refill_pool(self) -> None:
        shuffled = list(self._names)
        self._rng.shuffle(shuffled)
        self._pool.extend(shuffled)


def _fallback_names() -> list[str]:
    return list(_FALLBACK_NAMES)
