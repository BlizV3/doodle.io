import os
import pygame
import client.sounds as sounds
from client.utils import PALETTE, BRUSH_SIZES, BORDER, WHITE, ACCENT, draw_text, draw_panel_alpha

TOOL_BRUSH      = "brush"
TOOL_ERASER     = "eraser"
TOOL_FILL       = "fill"
TOOL_EYEDROPPER = "eyedropper"

SWATCH_SIZE = 22
SWATCH_PAD  = 2
BRUSH_STEP  = 28
BTN_SIZE    = 36
BTN_GAP     = 6

_TOOL_KEYS = [TOOL_BRUSH, TOOL_FILL, TOOL_EYEDROPPER, TOOL_ERASER, "clear"]

_ICON_FILES = {
    TOOL_BRUSH:      "pencil.png",
    TOOL_FILL:       "bucket.png",
    TOOL_EYEDROPPER: "pin.png",
    TOOL_ERASER:     "eraser.png",
    "clear":         "trash.png",
}

_COLORS = {
    TOOL_BRUSH:      ((80,  80, 200), (55,  55, 170)),
    TOOL_FILL:       ((60, 180, 100), (40, 150,  80)),
    TOOL_EYEDROPPER: ((80, 160, 220), (60, 130, 190)),
    TOOL_ERASER:     ((160,160, 160), (120,120, 120)),
    "clear":         ((220, 80,  80), (180, 50,  50)),
}

_ASSETS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))

_CURSOR_TOOLS = {TOOL_BRUSH, TOOL_FILL, TOOL_EYEDROPPER, TOOL_ERASER}


# Load an asset image and scale it to the given square size.
def _load_scaled(filename: str, size: int) -> pygame.Surface:
    path = os.path.join(_ASSETS_DIR, filename)
    img  = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))


class Toolbar:
    """Color palette + brush sizes + icon tool buttons.
    Only interactive when active=True (drawer's turn)."""

    # Load all tool icons and cursor images, set defaults, and apply the initial cursor state.
    def __init__(self, fonts: dict):
        self.fonts    = fonts
        self._active  = False
        self.color    = (0, 0, 0)
        self.size_idx = 1
        self._tool    = TOOL_BRUSH

        icon_size = BTN_SIZE - 10  # 26 px, centered in 36 px button
        self._icons: dict[str, pygame.Surface] = {
            k: _load_scaled(f, icon_size) for k, f in _ICON_FILES.items()
        }

        # 32×32 cursor surfaces with top-left hotspot (0, 0)
        self._cursors: dict[str, pygame.cursors.Cursor] = {
            k: pygame.cursors.Cursor((0, 0), _load_scaled(f, 32))
            for k, f in _ICON_FILES.items()
            if k in _CURSOR_TOOLS
        }
        self._last_cursor_key: str | None = None
        self._hovered_tool: str | None = None
        self._apply_cursor()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self._active

    # Set the active flag and re-apply the cursor to match the new state.
    @active.setter
    def active(self, value: bool):
        self._active = value
        self._apply_cursor()

    @property
    def tool(self) -> str:
        return self._tool

    # Set the current tool and re-apply the cursor image to match.
    @tool.setter
    def tool(self, value: str):
        self._tool = value
        self._apply_cursor()

    @property
    def current_size(self) -> int:
        return BRUSH_SIZES[self.size_idx]

    # ── Cursor ────────────────────────────────────────────────────────────────

    # Switch the system cursor to the active tool's icon, or restore the arrow when inactive.
    def _apply_cursor(self):
        key = self._tool if (self._active and self._tool in _CURSOR_TOOLS) else None
        if key == self._last_cursor_key:
            return
        self._last_cursor_key = key
        if key:
            pygame.mouse.set_cursor(self._cursors[key])
        else:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event, rect: pygame.Rect) -> bool:
        """Return True if 'clear' was clicked."""
        if not self._active:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False

        mx, my = event.pos

        # colour swatches — selecting a colour while in fill/eyedropper snaps back to pencil
        sx = rect.x + 6
        sy = rect.y + (rect.height - SWATCH_SIZE) // 2
        for i, col in enumerate(PALETTE):
            sr = pygame.Rect(sx + i * (SWATCH_SIZE + SWATCH_PAD), sy,
                             SWATCH_SIZE, SWATCH_SIZE)
            if sr.collidepoint(mx, my):
                self.color = col
                return False

        # brush size dots
        bx = sx + len(PALETTE) * (SWATCH_SIZE + SWATCH_PAD) + 12
        cy = rect.centery
        for i in range(len(BRUSH_SIZES)):
            cx2 = bx + i * BRUSH_STEP + 10
            if abs(mx - cx2) <= 14 and abs(my - cy) <= 14:
                self.size_idx = i
                return False

        # tool buttons (right-aligned)
        for key, btn_r in self._tool_buttons(rect).items():
            if btn_r.collidepoint(mx, my):
                sounds.play("click")
                if key == "clear":
                    return True
                self.tool = key
                return False

        return False

    # ── Render ────────────────────────────────────────────────────────────────

    # Draw the toolbar panel with color swatches, brush size dots, and tool icon buttons.
    def render(self, surface: pygame.Surface, rect: pygame.Rect):
        draw_panel_alpha(surface, rect,
                         bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 60), radius=0)

        if not self._active:
            msg = self.fonts["md"].render("Waiting for your turn…", True, (160, 190, 230))
            surface.blit(msg, msg.get_rect(center=rect.center))
            return

        sx = rect.x + 6
        sy = rect.y + (rect.height - SWATCH_SIZE) // 2

        # colour swatches
        for i, col in enumerate(PALETTE):
            sr = pygame.Rect(sx + i * (SWATCH_SIZE + SWATCH_PAD), sy,
                             SWATCH_SIZE, SWATCH_SIZE)
            pygame.draw.rect(surface, col, sr, border_radius=3)
            if col == self.color and self._tool in (TOOL_BRUSH, TOOL_FILL):
                pygame.draw.rect(surface, ACCENT, sr, 3, border_radius=3)
            else:
                pygame.draw.rect(surface, BORDER, sr, 1, border_radius=3)

        # brush size dots
        bx = sx + len(PALETTE) * (SWATCH_SIZE + SWATCH_PAD) + 12
        cy = rect.centery
        for i, sz in enumerate(BRUSH_SIZES):
            cx2 = bx + i * BRUSH_STEP + 10
            r   = sz // 2 + 1
            pygame.draw.circle(surface, (210, 225, 255), (cx2, cy), r)
            if i == self.size_idx and self._tool == TOOL_BRUSH:
                pygame.draw.circle(surface, ACCENT, (cx2, cy), r + 3, 2)

        # tool buttons
        mx, my = pygame.mouse.get_pos()
        new_hov = None
        for key, btn_r in self._tool_buttons(rect).items():
            active  = (key == self._tool)
            hovered = btn_r.collidepoint(mx, my)
            base, dark = _COLORS[key]
            bg = dark if (active or hovered) else base
            pygame.draw.rect(surface, bg, btn_r, border_radius=6)
            if active:
                pygame.draw.rect(surface, (255, 255, 255), btn_r, 2, border_radius=6)

            icon = self._icons[key]
            surface.blit(icon, icon.get_rect(center=btn_r.center))
            if hovered:
                new_hov = key

        if new_hov != self._hovered_tool:
            self._hovered_tool = new_hov
            if new_hov:
                sounds.play("hover")

    # Compute and return the rects for all right-aligned tool icon buttons.
    def _tool_buttons(self, rect: pygame.Rect) -> dict[str, pygame.Rect]:
        n     = len(_TOOL_KEYS)
        total = n * BTN_SIZE + (n - 1) * BTN_GAP
        bx    = rect.right - total - 8
        by    = rect.y + (rect.height - BTN_SIZE) // 2
        return {
            k: pygame.Rect(bx + i * (BTN_SIZE + BTN_GAP), by, BTN_SIZE, BTN_SIZE)
            for i, k in enumerate(_TOOL_KEYS)
        }
