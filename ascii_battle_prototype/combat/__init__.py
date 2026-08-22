"""Backend-oriented package for ASCII Tactical Combat Prototype v113."""

from .game import Game
from .results import BattleRequest, BattleResult

__all__ = ["BattleRequest", "BattleResult", "Game"]
