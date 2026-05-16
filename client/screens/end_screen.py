import pygame
import client.sounds as sounds
from client.utils import (
    WHITE, ACCENT, ACCENT_DARK, TEXT_DARK, TEXT_MID,
    BTN_ORANGE, BTN_ORANGE_DARK,
    AVATAR_COLORS, draw_text, draw_panel, get_background,
)

W, H = 1280, 720

MEDAL_COLORS = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]  # gold, silver, bronze


class EndScreen:
    """Final scoreboard shown when the game ends."""

    def __init__(self, fonts: dict, scores: list[dict]):
        self.fonts  = fonts
        self.scores = scores
        self._play_btn = pygame.Rect(W // 2 - 110, H - 110, 220, 54)
        self._hovered: str | None = None

    def handle_event(self, event) -> dict | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._play_btn.collidepoint(event.pos):
                sounds.play("click")
                return {"action": "play_again"}
        return None

    def update(self, dt_ms: int):
        pass

    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        draw_text(surface, "Game Over!", self.fonts["logo"], WHITE,
                  W // 2, 55, anchor="center")

        # podium-style top 3
        panel_w = 560
        panel   = pygame.Rect(W // 2 - panel_w // 2, 120, panel_w, 340)
        draw_panel(surface, panel, bg=WHITE, radius=14)

        draw_text(surface, "Final Scores", self.fonts["lg"], TEXT_DARK,
                  panel.centerx, panel.y + 24, anchor="center")

        y = panel.y + 70
        for i, entry in enumerate(self.scores):
            row_r = pygame.Rect(panel.x + 16, y, panel.width - 32, 46)

            # highlight top 3
            if i < 3:
                bg_col = (*MEDAL_COLORS[i], 40)
                hl     = pygame.Surface((row_r.width, row_r.height), pygame.SRCALPHA)
                hl.fill((*MEDAL_COLORS[i], 50))
                surface.blit(hl, row_r.topleft)

            # rank
            draw_text(surface, f"#{i + 1}", self.fonts["md"],
                      MEDAL_COLORS[i] if i < 3 else TEXT_MID,
                      row_r.x + 6, row_r.centery, anchor="midleft")

            # avatar
            av_col = AVATAR_COLORS[i % len(AVATAR_COLORS)]
            pygame.draw.circle(surface, av_col,
                               (row_r.x + 50, row_r.centery), 16)
            draw_text(surface, entry["name"][0].upper(), self.fonts["sm"], WHITE,
                      row_r.x + 50, row_r.centery, anchor="center")

            # name
            draw_text(surface, entry["name"], self.fonts["md"], TEXT_DARK,
                      row_r.x + 74, row_r.centery, anchor="midleft")

            # score
            draw_text(surface, f"{entry['score']} pts", self.fonts["md"], ACCENT,
                      row_r.right - 8, row_r.centery, anchor="midright")

            y += 52

        # play again button
        mx, my = pygame.mouse.get_pos()
        btn_col = BTN_ORANGE_DARK if self._play_btn.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, btn_col, self._play_btn, border_radius=10)
        draw_text(surface, "Play Again", self.fonts["lg"], WHITE,
                  self._play_btn.centerx, self._play_btn.centery, anchor="center")

        new_hov = "play" if self._play_btn.collidepoint(mx, my) else None
        if new_hov != self._hovered:
            self._hovered = new_hov
            if new_hov:
                sounds.play("hover")
