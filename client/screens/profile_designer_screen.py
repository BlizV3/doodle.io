import os
import pygame
from client.utils import (
    WHITE, ACCENT, BORDER,
    BTN_ORANGE, BTN_ORANGE_DARK,
    PALETTE, BRUSH_SIZES,
    draw_text, draw_panel_alpha, get_background,
)
from client.components.canvas import DrawingCanvas
from client.components.toolbar import TOOL_BRUSH, TOOL_ERASER, TOOL_FILL
import client.sounds as sounds
import client.pfp as pfp_mod

W, H = 1280, 720

_CANVAS_X    = 410
_CANVAS_Y    = 50
_CANVAS_SIZE = 460

_SWATCH_SIZE = 22
_SWATCH_PAD  = 2
_BRUSH_STEP  = 28
_BTN_SIZE    = 36
_BTN_GAP     = 6

_TOOL_COLORS = {
    TOOL_BRUSH:  ((80,  80, 200), (55,  55, 170)),
    TOOL_FILL:   ((60, 180, 100), (40, 150,  80)),
    TOOL_ERASER: ((160,160, 160), (120,120, 120)),
}


class ProfileDesignerScreen:
    def __init__(self, fonts: dict, prev_name: str = ""):
        self.fonts      = fonts
        self._prev_name = prev_name

        self._canvas = DrawingCanvas(_CANVAS_SIZE, _CANVAS_SIZE)
        self._canvas.active = True
        self._canvas_rect   = pygame.Rect(_CANVAS_X, _CANVAS_Y, _CANVAS_SIZE, _CANVAS_SIZE)

        self._tool     = TOOL_BRUSH
        self._color    = (0, 0, 0)
        self._size_idx = 1

        # Vertical layout beneath the canvas
        _bottom      = _CANVAS_Y + _CANVAS_SIZE
        _swatch_y    = _bottom + 8
        _size_y      = _swatch_y + _SWATCH_SIZE + 14
        _tool_y      = _size_y + 36
        _btn_y       = _tool_y + _BTN_SIZE + 4

        self._swatch_y = _swatch_y
        self._size_y   = _size_y
        self._tool_y   = _tool_y

        # Tool button rects (Brush, Fill, Eraser)
        _tools      = [TOOL_BRUSH, TOOL_FILL, TOOL_ERASER]
        _tool_total = len(_tools) * _BTN_SIZE + (len(_tools) - 1) * _BTN_GAP
        _tool_x0    = _CANVAS_X + (_CANVAS_SIZE - _tool_total) // 2
        self._tool_btns: dict[str, pygame.Rect] = {
            t: pygame.Rect(_tool_x0 + i * (_BTN_SIZE + _BTN_GAP), _tool_y, _BTN_SIZE, _BTN_SIZE)
            for i, t in enumerate(_tools)
        }

        # Action buttons
        self._clear_btn  = pygame.Rect(_CANVAS_X,                          _btn_y, 110, 40)
        self._cancel_btn = pygame.Rect(_CANVAS_X + _CANVAS_SIZE // 2 - 75, _btn_y, 150, 40)
        self._save_btn   = pygame.Rect(_CANVAS_X + _CANVAS_SIZE - 150,     _btn_y, 150, 40)

        # Tool icons
        _assets_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        _icon_files = {
            TOOL_BRUSH:  "pencil.png",
            TOOL_FILL:   "bucket.png",
            TOOL_ERASER: "eraser.png",
        }
        self._icons: dict[str, pygame.Surface] = {}
        for key, fname in _icon_files.items():
            try:
                img = pygame.image.load(os.path.join(_assets_dir, fname)).convert_alpha()
                self._icons[key] = pygame.transform.smoothscale(img, (_BTN_SIZE - 10, _BTN_SIZE - 10))
            except Exception:
                pass

        self._hovered: str | None = None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _swatch_rects(self) -> list[tuple[tuple, pygame.Rect]]:
        total = len(PALETTE) * (_SWATCH_SIZE + _SWATCH_PAD) - _SWATCH_PAD
        sx    = _CANVAS_X + (_CANVAS_SIZE - total) // 2
        return [
            (col, pygame.Rect(sx + i * (_SWATCH_SIZE + _SWATCH_PAD),
                              self._swatch_y, _SWATCH_SIZE, _SWATCH_SIZE))
            for i, col in enumerate(PALETTE)
        ]

    def _size_centers(self) -> list[tuple[int, int]]:
        total = len(BRUSH_SIZES) * _BRUSH_STEP
        bx    = _CANVAS_X + (_CANVAS_SIZE - total) // 2 + _BRUSH_STEP // 2
        return [(bx + i * _BRUSH_STEP, self._size_y) for i in range(len(BRUSH_SIZES))]

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event) -> dict | None:
        # Sync canvas tool/color/size before passing events
        self._canvas.color = self._color
        self._canvas.size  = BRUSH_SIZES[self._size_idx]
        self._canvas.tool  = self._tool
        self._canvas.handle_event(event, self._canvas_rect)

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            if event.key == pygame.K_z and (mods & pygame.KMOD_CTRL):
                self._canvas.undo()
            elif event.key == pygame.K_y and (mods & pygame.KMOD_CTRL):
                self._canvas.redo()
            return None

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None

        mx, my = event.pos

        # Color swatches
        for col, r in self._swatch_rects():
            if r.collidepoint(mx, my):
                self._color = col
                sounds.play("click")
                return None

        # Brush sizes
        for i, (cx2, cy2) in enumerate(self._size_centers()):
            if abs(mx - cx2) <= 14 and abs(my - cy2) <= 14:
                self._size_idx = i
                sounds.play("click")
                return None

        # Tool buttons
        for tool, r in self._tool_btns.items():
            if r.collidepoint(mx, my):
                self._tool = tool
                sounds.play("click")
                return None

        # Action buttons
        if self._clear_btn.collidepoint(mx, my):
            sounds.play("click")
            self._canvas.clear()
            return None

        if self._cancel_btn.collidepoint(mx, my):
            sounds.play("click")
            return {"action": "back", "prev_name": self._prev_name}

        if self._save_btn.collidepoint(mx, my):
            sounds.play("click")
            return self._save_pfp()

        return None

    def _save_pfp(self) -> dict:
        assets_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets", "pfps")
        )
        os.makedirs(assets_dir, exist_ok=True)
        out_path = os.path.join(assets_dir, "custom.png")
        scaled = pygame.transform.smoothscale(self._canvas.surface, (256, 256))
        pygame.image.save(scaled, out_path)
        pfp_mod.clear_cache()

        pfp_idx = 0
        try:
            files = sorted(f for f in os.listdir(assets_dir)
                           if f.lower().endswith((".png", ".jpg", ".jpeg")))
            pfp_idx = next((i for i, f in enumerate(files) if f.lower() == "custom.png"), 0)
        except Exception:
            pass

        return {"action": "pfp_saved", "pfp_idx": pfp_idx, "prev_name": self._prev_name}

    def update(self, dt_ms: int):
        pass

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        # ── Left panel ────────────────────────────────────────────────────────
        left_cx = _CANVAS_X // 2

        draw_text(surface, "Profile", self.fonts["xl"], WHITE,
                  left_cx, 42, anchor="center")
        draw_text(surface, "Designer", self.fonts["xl"], WHITE,
                  left_cx, 90, anchor="center")

        # Live circular preview
        _prev_size = 160
        _prev_cy   = 260
        pygame.draw.circle(surface, ACCENT, (left_cx, _prev_cy), _prev_size // 2 + 4)
        prev = pygame.transform.smoothscale(self._canvas.surface, (_prev_size, _prev_size))
        prev = prev.convert_alpha()
        mask = pygame.Surface((_prev_size, _prev_size), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.circle(mask, (255, 255, 255, 255),
                           (_prev_size // 2, _prev_size // 2), _prev_size // 2)
        prev.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(prev, (left_cx - _prev_size // 2, _prev_cy - _prev_size // 2))

        draw_text(surface, "Preview", self.fonts["sm"], (210, 235, 255),
                  left_cx, _prev_cy + _prev_size // 2 + 16, anchor="center")
        draw_text(surface, "Ctrl+Z  Undo", self.fonts["sm"], (150, 175, 215),
                  left_cx, _prev_cy + _prev_size // 2 + 44, anchor="center")
        draw_text(surface, "Ctrl+Y  Redo", self.fonts["sm"], (150, 175, 215),
                  left_cx, _prev_cy + _prev_size // 2 + 64, anchor="center")

        # ── Canvas ────────────────────────────────────────────────────────────
        self._canvas.render(surface, _CANVAS_X, _CANVAS_Y)

        mx, my = pygame.mouse.get_pos()

        # ── Color swatches ────────────────────────────────────────────────────
        for col, r in self._swatch_rects():
            pygame.draw.rect(surface, col, r, border_radius=3)
            if col == self._color and self._tool in (TOOL_BRUSH, TOOL_FILL):
                pygame.draw.rect(surface, ACCENT, r, 3, border_radius=3)
            else:
                pygame.draw.rect(surface, BORDER, r, 1, border_radius=3)

        # ── Brush sizes ───────────────────────────────────────────────────────
        for i, (cx2, cy2) in enumerate(self._size_centers()):
            sz = BRUSH_SIZES[i]
            r  = sz // 2 + 1
            pygame.draw.circle(surface, (210, 225, 255), (cx2, cy2), r)
            if i == self._size_idx:
                pygame.draw.circle(surface, ACCENT, (cx2, cy2), r + 3, 2)

        # ── Tool buttons ──────────────────────────────────────────────────────
        for tool, r in self._tool_btns.items():
            active  = (tool == self._tool)
            hovered = r.collidepoint(mx, my)
            base, dark = _TOOL_COLORS[tool]
            bg = dark if (active or hovered) else base
            pygame.draw.rect(surface, bg, r, border_radius=6)
            if active:
                pygame.draw.rect(surface, WHITE, r, 2, border_radius=6)
            if tool in self._icons:
                ic = self._icons[tool]
                surface.blit(ic, ic.get_rect(center=r.center))

        # ── Action buttons ────────────────────────────────────────────────────
        cc = (200, 55, 55) if self._clear_btn.collidepoint(mx, my) else (170, 40, 40)
        pygame.draw.rect(surface, cc, self._clear_btn, border_radius=8)
        draw_text(surface, "Clear", self.fonts["btn_md"], WHITE,
                  self._clear_btn.centerx, self._clear_btn.centery, anchor="center")

        cancel_c = (100, 110, 145) if self._cancel_btn.collidepoint(mx, my) else (80, 90, 120)
        pygame.draw.rect(surface, cancel_c, self._cancel_btn, border_radius=8)
        draw_text(surface, "Cancel", self.fonts["btn_md"], WHITE,
                  self._cancel_btn.centerx, self._cancel_btn.centery, anchor="center")

        save_c = BTN_ORANGE_DARK if self._save_btn.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, save_c, self._save_btn, border_radius=8)
        draw_text(surface, "Set as PFP", self.fonts["btn_md"], WHITE,
                  self._save_btn.centerx, self._save_btn.centery, anchor="center")

        # ── Hover sounds ──────────────────────────────────────────────────────
        new_hov = None
        if self._clear_btn.collidepoint(mx, my):   new_hov = "clear"
        elif self._cancel_btn.collidepoint(mx, my): new_hov = "cancel"
        elif self._save_btn.collidepoint(mx, my):   new_hov = "save"
        else:
            for t, r in self._tool_btns.items():
                if r.collidepoint(mx, my):
                    new_hov = f"tool_{t}"; break
        if new_hov != self._hovered:
            self._hovered = new_hov
            if new_hov:
                sounds.play("hover")
