import io
import base64
import pygame
from shared.protocol import DRAW, DRAW_FILL, DRAW_CLEAR
from client.components.toolbar import (
    TOOL_BRUSH, TOOL_ERASER, TOOL_FILL, TOOL_EYEDROPPER,
)


class DrawingCanvas:
    """White drawing surface.

    handle_event() returns a list of dicts – either protocol messages to send
    to the server, or local events:
      {"type": "eyedropper_pick", "color": [r, g, b]}
    """

    def __init__(self, width: int, height: int):
        self.width   = width
        self.height  = height
        self.surface = pygame.Surface((width, height))
        self.surface.fill((255, 255, 255))

        self.active    = False
        self.color     = (0, 0, 0)
        self.size      = 6
        self.tool      = TOOL_BRUSH

        self._drawing  = False
        self._last_pos: tuple[int, int] | None = None

        self._history: list[pygame.Surface] = []
        self._hist_idx: int = -1
        self._save_snapshot()   # blank canvas as initial state

    # ── Local input ──────────────────────────────────────────────────────────

    def handle_event(self, event, canvas_rect: pygame.Rect) -> list[dict]:
        if not self.active:
            return []

        msgs = []

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not canvas_rect.collidepoint(event.pos):
                return []
            lx = event.pos[0] - canvas_rect.x
            ly = event.pos[1] - canvas_rect.y

            if self.tool == TOOL_FILL:
                self.flood_fill(lx, ly, self.color)
                msgs.append({"type": DRAW_FILL,
                              "x": lx, "y": ly, "color": list(self.color)})

            elif self.tool == TOOL_EYEDROPPER:
                picked = self.get_color_at(lx, ly)
                msgs.append({"type": "eyedropper_pick", "color": list(picked)})

            else:   # BRUSH or ERASER
                self._drawing  = True
                self._last_pos = (lx, ly)
                color, size    = self._brush_params()
                self._draw_circle(lx, ly, color, size)
                msgs.append({"type": DRAW,
                              "x1": lx, "y1": ly, "x2": lx, "y2": ly,
                              "color": list(color), "size": size})

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drawing:
                self._save_snapshot()
            self._drawing  = False
            self._last_pos = None

        elif event.type == pygame.MOUSEMOTION and self._drawing:
            if self.tool not in (TOOL_BRUSH, TOOL_ERASER):
                return []
            lx = max(0, min(event.pos[0] - canvas_rect.x, self.width  - 1))
            ly = max(0, min(event.pos[1] - canvas_rect.y, self.height - 1))
            color, size = self._brush_params()
            if self._last_pos:
                self._draw_line(self._last_pos[0], self._last_pos[1], lx, ly, color, size)
                msgs.append({"type": DRAW,
                              "x1": self._last_pos[0], "y1": self._last_pos[1],
                              "x2": lx, "y2": ly,
                              "color": list(color), "size": size})
            self._last_pos = (lx, ly)

        return msgs

    def _brush_params(self) -> tuple[tuple, int]:
        if self.tool == TOOL_ERASER:
            return (255, 255, 255), self.size * 3
        return self.color, self.size

    # ── Remote events ────────────────────────────────────────────────────────

    def apply_draw(self, msg: dict):
        color = tuple(msg["color"])
        size  = msg["size"]
        x1, y1, x2, y2 = msg["x1"], msg["y1"], msg["x2"], msg["y2"]
        if x1 == x2 and y1 == y2:
            self._draw_circle(x1, y1, color, size)
        else:
            self._draw_line(x1, y1, x2, y2, color, size)

    def apply_fill(self, msg: dict):
        self.flood_fill(msg["x"], msg["y"], tuple(msg["color"]))

    def apply_clear(self):
        """Remote-triggered clear — does not touch undo history."""
        self.surface.fill((255, 255, 255))
        self._last_pos = None
        self._drawing  = False

    def clear(self):
        """Local clear button — saves an undo snapshot."""
        self.surface.fill((255, 255, 255))
        self._last_pos = None
        self._drawing  = False
        self._save_snapshot()

    def reset(self):
        """New round — wipe canvas and reset undo history."""
        self.surface.fill((255, 255, 255))
        self._last_pos = None
        self._drawing  = False
        self._history  = []
        self._hist_idx = -1
        self._save_snapshot()

    # ── Fill tool ─────────────────────────────────────────────────────────────

    def flood_fill(self, x: int, y: int, fill_color: tuple):
        """Scanline flood fill via pygame.PixelArray (fast C-backed access)."""
        x, y = int(x), int(y)
        if not (0 <= x < self.width and 0 <= y < self.height):
            return

        fill_c   = tuple(int(c) for c in fill_color[:3])
        target_c = tuple(self.surface.get_at((x, y)))[:3]
        if target_c == fill_c:
            return

        w, h = self.width, self.height
        pxa          = pygame.PixelArray(self.surface)
        target_mapped = pxa[x, y]
        fill_mapped   = self.surface.map_rgb(*fill_c)

        stack = [(x, y)]
        while stack:
            sx, sy = stack.pop()
            if not (0 <= sx < w and 0 <= sy < h):
                continue
            if pxa[sx, sy] != target_mapped:
                continue

            # expand left / right
            lx = sx
            while lx > 0 and pxa[lx - 1, sy] == target_mapped:
                lx -= 1
            rx = sx
            while rx < w - 1 and pxa[rx + 1, sy] == target_mapped:
                rx += 1

            # fill span
            for i in range(lx, rx + 1):
                pxa[i, sy] = fill_mapped

            # seed above and below
            for ny in (sy - 1, sy + 1):
                if 0 <= ny < h:
                    in_run = False
                    for nx in range(lx, rx + 1):
                        if pxa[nx, ny] == target_mapped:
                            if not in_run:
                                stack.append((nx, ny))
                                in_run = True
                        else:
                            in_run = False

        del pxa   # release surface lock
        self._save_snapshot()

    # ── Eyedropper tool ───────────────────────────────────────────────────────

    def get_color_at(self, x: int, y: int) -> tuple[int, int, int]:
        x = max(0, min(int(x), self.width  - 1))
        y = max(0, min(int(y), self.height - 1))
        return tuple(self.surface.get_at((x, y)))[:3]

    # ── Undo / Redo ──────────────────────────────────────────────────────────

    def _save_snapshot(self):
        if self._hist_idx < len(self._history) - 1:
            self._history = self._history[:self._hist_idx + 1]
        snap = pygame.Surface((self.width, self.height))
        snap.blit(self.surface, (0, 0))
        self._history.append(snap)
        self._hist_idx = len(self._history) - 1
        if len(self._history) > 50:
            self._history.pop(0)
            self._hist_idx -= 1

    def undo(self) -> bool:
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self.surface.blit(self._history[self._hist_idx], (0, 0))
            self._drawing  = False
            self._last_pos = None
            return True
        return False

    def redo(self) -> bool:
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self.surface.blit(self._history[self._hist_idx], (0, 0))
            return True
        return False

    def get_snapshot_b64(self) -> str:
        """Encode current surface as base64 PNG string."""
        buf = io.BytesIO()
        pygame.image.save(self.surface, buf, ".png")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def apply_snapshot(self, b64: str):
        """Decode a base64 PNG and blit it onto the canvas."""
        buf = io.BytesIO(base64.b64decode(b64))
        img = pygame.image.load(buf, ".png")
        self.surface.blit(pygame.transform.scale(img, (self.width, self.height)), (0, 0))
        self._drawing  = False
        self._last_pos = None

    # ── Render ───────────────────────────────────────────────────────────────

    def render(self, screen: pygame.Surface, x: int, y: int):
        screen.blit(self.surface, (x, y))
        pygame.draw.rect(screen, (200, 200, 200),
                         pygame.Rect(x - 1, y - 1, self.width + 2, self.height + 2), 1)

    # ── Primitives ────────────────────────────────────────────────────────────

    def _draw_circle(self, x, y, color, size):
        pygame.draw.circle(self.surface, color, (x, y), max(1, size // 2))

    def _draw_line(self, x1, y1, x2, y2, color, size):
        pygame.draw.line(self.surface, color, (x1, y1), (x2, y2), max(1, size))
        pygame.draw.circle(self.surface, color, (x1, y1), max(1, size // 2))
        pygame.draw.circle(self.surface, color, (x2, y2), max(1, size // 2))
