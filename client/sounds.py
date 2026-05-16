"""
Thin wrapper around pygame.mixer for one-shot sound effects.
Call init() once after pygame.init(), then play("Name") anywhere.
"""
import os
import pygame

_DIR   = os.path.join(os.path.dirname(__file__), "assets", "sounds")
_cache: dict[str, "pygame.mixer.Sound | None"] = {}
_ready = False


def init():
    global _ready
    try:
        pygame.mixer.init()
        _ready = True
    except pygame.error:
        _ready = False


def play(name: str):
    if not _ready:
        return
    if name not in _cache:
        _cache[name] = _load(name)
    snd = _cache[name]
    if snd is not None:
        snd.play()


def _load(name: str) -> "pygame.mixer.Sound | None":
    for ext in (".ogg", ".wav", ".mp3"):
        path = os.path.join(_DIR, name + ext)
        if os.path.isfile(path):
            try:
                return pygame.mixer.Sound(path)
            except pygame.error:
                pass
    return None
