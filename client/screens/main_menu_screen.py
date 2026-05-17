import os
import pygame
from client.utils import WHITE, draw_text
import client.sounds as sounds

W, H = 1280, 720

_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets")
)

# ── asset loaders (identical to toolbar.py) ───────────────────────────────────

# Load an asset image and scale it to the given square size.
def _load_scaled(filename: str, size: int) -> pygame.Surface:
    path = os.path.join(_ASSETS_DIR, filename)
    img  = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))

# Load and scale the default background image to 1280×720.
def _load_bg() -> pygame.Surface:
    path = os.path.join(_ASSETS_DIR, "backgrounds", "default.png")
    img  = pygame.image.load(path).convert()
    return pygame.transform.smoothscale(img, (W, H))


class MainMenuScreen:
    # Panel colours (RGBA) — dark navy at 15 % opacity
    _PANEL_NORMAL = (10, 22, 60, 38)
    _PANEL_HOVER  = (18, 36, 90, 60)
    _BORDER_COL   = (10, 22, 60, 64)   # same navy, 25 % opacity

    # Load background, card icons, and compute button rects for JOIN and CREATE.
    def __init__(self, fonts: dict, name: str, pfp_idx: int = 0, pfp_surf=None):
        self.fonts   = fonts
        self.name    = name
        self.pfp_idx = pfp_idx
        self.error   = ""

        self._bg          = _load_bg()
        self._icon_join   = _load_scaled("enter.png",  230)
        self._icon_create = _load_scaled("build.png",  230)

        raw = pygame.image.load(
            os.path.join(_ASSETS_DIR, "thumbnail.png")
        ).convert_alpha()
        rw, rh = raw.get_size()
        scale  = min(1200 / rw, 220 / rh)
        self._thumbnail = pygame.transform.smoothscale(
            raw, (min(int(rw * scale), W - 40), int(rh * scale))
        )

        cx = W // 2
        btn_w, btn_h = 329, 410
        gap           = 28
        btn_y         = 260
        # JOIN left, CREATE right — matches reference layout
        self._join_btn   = pygame.Rect(cx - gap // 2 - btn_w, btn_y, btn_w, btn_h)
        self._create_btn = pygame.Rect(cx + gap // 2,          btn_y, btn_w, btn_h)
        self._hovered: str | None = None

    # ── events ────────────────────────────────────────────────────────────────

    # Detect clicks on the CREATE or JOIN buttons and return the corresponding action dict.
    def handle_event(self, event) -> dict | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._create_btn.collidepoint(event.pos):
                sounds.play("click")
                return {"action": "create"}
            if self._join_btn.collidepoint(event.pos):
                sounds.play("click")
                return {"action": "join"}
        return None

    def update(self, dt_ms: int):
        pass

    # ── render ────────────────────────────────────────────────────────────────

    # Draw the background, logo thumbnail, and the two large menu card buttons.
    def render(self, surface: pygame.Surface):
        surface.blit(self._bg, (0, 0))

        # ── Logo thumbnail ────────────────────────────────────────────────────
        tw, th = self._thumbnail.get_size()
        surface.blit(self._thumbnail, (W // 2 - tw // 2, 18))

        # ── Buttons ───────────────────────────────────────────────────────────
        self._draw_btn(surface, self._join_btn,   self._icon_join,   "JOIN")
        self._draw_btn(surface, self._create_btn, self._icon_create, "CREATE")

        if self.error:
            draw_text(surface, self.error, self.fonts["sm"], (255, 110, 110),
                      W // 2, self._join_btn.bottom + 20, anchor="midtop")

        mx, my = pygame.mouse.get_pos()
        new_hov = None
        if self._create_btn.collidepoint(mx, my):   new_hov = "create"
        elif self._join_btn.collidepoint(mx, my):   new_hov = "join"
        if new_hov != self._hovered:
            self._hovered = new_hov
            if new_hov:
                sounds.play("hover")

    # ── helpers ───────────────────────────────────────────────────────────────

    # Draw a semi-transparent card button with a centred icon and a label pinned to the bottom.
    def _draw_btn(self, surface: pygame.Surface, btn: pygame.Rect,
                  icon: pygame.Surface, label: str):
        mx, my  = pygame.mouse.get_pos()
        hovered = btn.collidepoint(mx, my)

        # Semi-transparent blue panel
        panel = pygame.Surface((btn.width, btn.height), pygame.SRCALPHA)
        pygame.draw.rect(panel,
                         self._PANEL_HOVER if hovered else self._PANEL_NORMAL,
                         panel.get_rect(), border_radius=26)
        surface.blit(panel, btn.topleft)

        # Thin border
        border = pygame.Surface((btn.width, btn.height), pygame.SRCALPHA)
        pygame.draw.rect(border, self._BORDER_COL,
                         border.get_rect(), 2, border_radius=26)
        surface.blit(border, btn.topleft)

        # Icon — centred in the space above the label
        label_block = self.fonts["xl"].get_linesize() + 10
        icon_zone_h = btn.height - label_block - 10
        icon_cy     = btn.y + icon_zone_h // 2
        surface.blit(icon, icon.get_rect(center=(btn.centerx, icon_cy)))

        # Label pinned to bottom
        draw_text(surface, label, self.fonts["xl"], WHITE,
                  btn.centerx, btn.bottom - label_block, anchor="midtop")
