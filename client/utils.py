"""Shared drawing helpers for all screens / components."""
import os
import pygame

# ── Palette ───────────────────────────────────────────────────────────────────
PALETTE = [
    (0,   0,   0  ), (255, 255, 255), (127, 127, 127), (195, 195, 195),
    (136,  0,  21 ), (237,  28,  36), (255, 127,  39), (255, 242,   0),
    ( 34, 177,  76), ( 0,  162, 232), ( 63,  72, 204), (163,  73, 164),
    (255, 174, 201), (255, 201,  14), (181, 230,  29), (153, 217, 234),
]

BRUSH_SIZES = [3, 6, 10, 16, 24]

# ── Colours ───────────────────────────────────────────────────────────────────
BG          = (250, 248, 243)   # warm sketchbook paper
WHITE       = (255, 255, 255)
PANEL       = (255, 255, 255)
BORDER      = (205, 210, 222)   # blue-tinted border
TEXT_DARK   = ( 35,  45,  70)   # deep navy for readability
TEXT_MID    = ( 95, 105, 125)
TEXT_LIGHT  = (155, 165, 182)
ACCENT      = ( 40, 110, 250)   # bold marker blue
ACCENT_DARK = ( 20,  78, 210)
BTN_ORANGE      = (225, 110,  40)   # warm orange for UI buttons
BTN_ORANGE_DARK = (185,  82,  18)
CORRECT     = ( 39, 174,  96)
SYSTEM      = (120, 132, 148)
HEADER_A    = ( 50, 118, 248)   # top-bar gradient left  (deep blue)
HEADER_B    = (108, 178, 255)   # top-bar gradient right (sky blue)
ORANGE      = (255, 142,  83)

AVATAR_COLORS = [
    (231, 76,  60 ), ( 52, 152, 219), ( 46, 204, 113), (230, 126,  34),
    (155,  89, 182), (241, 196,  15), ( 26, 188, 156), ( 52,  73,  94),
]


# ── Low-level helpers ─────────────────────────────────────────────────────────

def draw_panel(surface: pygame.Surface, rect, bg=PANEL, border_color=BORDER, radius=8):
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    pygame.draw.rect(surface, border_color, rect, 2, border_radius=radius)


def draw_panel_alpha(surface: pygame.Surface, rect,
                     bg_rgba=(10, 22, 60, 38), border_rgba=(80, 140, 255, 80),
                     radius=8):
    """Draw a semi-transparent rounded panel using SRCALPHA."""
    srf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(srf, bg_rgba, srf.get_rect(), border_radius=radius)
    surface.blit(srf, rect.topleft)
    if border_rgba:
        brd = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(brd, border_rgba, brd.get_rect(), 2, border_radius=radius)
        surface.blit(brd, rect.topleft)


def draw_text(surface: pygame.Surface, text: str, font: pygame.font.Font,
              color, x: int, y: int, anchor: str = "topleft") -> pygame.Rect:
    surf = font.render(text, True, color)
    r    = surf.get_rect()
    setattr(r, anchor, (x, y))
    surface.blit(surf, r)
    return r


def draw_button(surface: pygame.Surface, rect, text: str, font: pygame.font.Font,
                bg=ACCENT, fg=WHITE, hover_bg=ACCENT_DARK,
                radius: int = 8, disabled: bool = False) -> bool:
    """Draw a button; returns True if it was clicked this frame."""
    mx, my    = pygame.mouse.get_pos()
    hovered   = rect.collidepoint(mx, my) and not disabled
    color     = (180, 180, 180) if disabled else (hover_bg if hovered else bg)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    draw_text(surface, text, font, fg, rect.centerx, rect.centery, anchor="center")
    return False   # click detection is done via event handling, not polling


def gradient_rect(surface: pygame.Surface, rect, color_a, color_b):
    """Horizontal gradient fill."""
    w = max(rect.width, 1)
    for x in range(rect.width):
        t   = x / w
        col = tuple(int(color_a[i] + (color_b[i] - color_a[i]) * t) for i in range(3))
        pygame.draw.line(surface, col,
                         (rect.x + x, rect.y),
                         (rect.x + x, rect.y + rect.height - 1))


_bg_cache: pygame.Surface | None = None

def get_background() -> pygame.Surface:
    """Load backgrounds/default.png once and cache it for the lifetime of the process."""
    global _bg_cache
    if _bg_cache is None:
        path = os.path.join(os.path.dirname(__file__), "assets", "backgrounds", "default.png")
        try:
            img      = pygame.image.load(path).convert()
            _bg_cache = pygame.transform.smoothscale(img, (1280, 720))
        except Exception:
            _bg_cache = pygame.Surface((1280, 720))
            _bg_cache.fill(BG)
    return _bg_cache


def make_fonts() -> dict[str, pygame.font.Font]:
    """Return a dict of named fonts, preferring handwriting-style for the skribbl feel."""
    candidates = ["inkfree", "segoeprint", "comicsansms", "segoeui", "arial", "helvetica", "freesansbold"]
    base_name = None
    for c in candidates:
        try:
            pygame.font.SysFont(c, 16)
            base_name = c
            break
        except Exception:
            pass

    def f(size, bold=False):
        try:
            return pygame.font.SysFont(base_name or "", size, bold=bold)
        except Exception:
            return pygame.font.Font(None, size)

    return {
        "sm":     f(17),
        "md":     f(21),
        "lg":     f(27, bold=True),
        "xl":     f(37, bold=True),
        "hint":   f(33, bold=True),
        "logo":   f(54, bold=True),
        "btn_sm": f(17, bold=True),
        "btn_md": f(21, bold=True),
        "btn_lg": f(27, bold=True),
    }
