"""Shared pfp loading and circular-crop helpers. Results are cached per radius."""
import os
import pygame

_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "assets", "pfps")
)

_cache: dict[int, list[pygame.Surface]] = {}


# Scale a surface to a circle of the given radius using an SRCALPHA mask.
def circle_crop(surf: pygame.Surface, radius: int) -> pygame.Surface:
    d = radius * 2
    scaled = pygame.transform.smoothscale(surf, (d, d)).convert_alpha()
    mask = pygame.Surface((d, d), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    pygame.draw.circle(mask, (255, 255, 255, 255), (radius, radius), radius)
    result = scaled.copy()
    result.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return result


# Load and circle-crop all pfp images from the pfps asset dir, cached per radius.
def load_pfps(radius: int) -> list[pygame.Surface]:
    if radius in _cache:
        return _cache[radius]
    images = []
    if os.path.isdir(_ASSETS_DIR):
        for fname in sorted(os.listdir(_ASSETS_DIR)):
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                try:
                    raw = pygame.image.load(
                        os.path.join(_ASSETS_DIR, fname)
                    ).convert_alpha()
                    images.append(circle_crop(raw, radius))
                except Exception:
                    pass
    _cache[radius] = images
    return images


# Return a circle-cropped pfp surface by index, or None if the index is out of range.
def get_pfp(idx: int, radius: int) -> "pygame.Surface | None":
    pfps = load_pfps(radius)
    return pfps[idx] if 0 <= idx < len(pfps) else None


def clear_cache():
    _cache.clear()
