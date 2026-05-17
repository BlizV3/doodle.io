import pygame
from client.utils import (
    draw_text, draw_panel_alpha, WHITE, ACCENT, ORANGE
)

HINT_SPACE = 22   # px between hint characters


class HUD:
    """Top bar: round info | word hint | timer."""

    # Initialize the HUD with empty round label, hint, and timer; ready to receive update calls.
    def __init__(self, fonts: dict, height: int = 80):
        self.fonts       = fonts
        self.height      = height
        self.round_text  = ""
        self.hint: list[str] = []
        self.timer       = 0
        self.drawer_name = ""
        self.is_drawing  = False   # local player is the drawer

    # Store all round-start data so the HUD reflects the current round state.
    def update_round(self, drawer: str, round_n: int, total: int, hint: list[str],
                     time_secs: int, local_is_drawing: bool):
        self.drawer_name = drawer
        self.round_text  = f"Round {round_n} of {total}"
        self.hint        = hint
        self.timer       = time_secs
        self.is_drawing  = local_is_drawing

    def update_hint(self, hint: list[str]):
        self.hint = hint

    def update_timer(self, remaining: int):
        self.timer = remaining

    # Draw the HUD bar: round label, drawer name, word hint, and the countdown timer.
    def render(self, surface: pygame.Surface, rect: pygame.Rect):
        draw_panel_alpha(surface, rect,
                         bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 60), radius=0)

        # ── round label (left) ────────────────────────────────────────────────
        draw_text(surface, self.round_text, self.fonts["md"], WHITE,
                  rect.x + 16, rect.centery, anchor="midleft")

        # ── drawer label (left, below round) ─────────────────────────────────
        if self.drawer_name:
            label = "You are drawing!" if self.is_drawing else f"{self.drawer_name} is drawing"
            draw_text(surface, label, self.fonts["sm"], (185, 218, 255),
                      rect.x + 16, rect.centery + 16, anchor="midleft")

        # ── word hint (centre) ────────────────────────────────────────────────
        self._draw_hint(surface, rect)

        # ── timer (right) ─────────────────────────────────────────────────────
        timer_color = (255, 80, 80) if self.timer <= 10 else WHITE
        draw_text(surface, str(self.timer), self.fonts["xl"], timer_color,
                  rect.right - 20, rect.centery, anchor="midright")

    # Draw each hint character centered in the HUD, using underlines for hidden letters.
    def _draw_hint(self, surface: pygame.Surface, rect: pygame.Rect):
        if not self.hint:
            return

        font     = self.fonts["hint"]
        chars    = self.hint
        char_w   = font.size("W")[0]
        gap      = 8
        total_w  = len(chars) * (char_w + gap) - gap
        start_x  = rect.centerx - total_w // 2
        y        = rect.centery - 10

        for i, ch in enumerate(chars):
            x = start_x + i * (char_w + gap)
            if ch == " ":
                continue
            elif ch == "_":
                line_y = y + font.get_ascent() + 4
                pygame.draw.line(surface, WHITE,
                                 (x, line_y), (x + char_w, line_y), 3)
            else:
                draw_text(surface, ch.upper(), font, WHITE, x, y, anchor="topleft")
