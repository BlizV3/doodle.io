import pygame
from client.utils import BORDER, WHITE, ACCENT, AVATAR_COLORS, draw_text, draw_panel_alpha
from client.pfp import get_pfp

_NAME_COL  = (210, 235, 255)
_SCORE_COL = (160, 190, 230)
_DRAW_HL   = ( 40,  80, 160)


class Scoreboard:
    """Left-side panel showing all players, scores, and drawing indicator."""

    AVATAR_R   = 18
    ROW_H      = 60
    HEADER_H   = 36

    def __init__(self, fonts: dict):
        self.fonts   = fonts
        self.players: list[dict] = []   # [{name, score, is_drawing, pfp_idx}]

    def update(self, players: list[dict]):
        self.players = players

    def render(self, surface: pygame.Surface, rect: pygame.Rect):
        draw_panel_alpha(surface, rect,
                         bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 60), radius=0)

        # header
        header_r = pygame.Rect(rect.x, rect.y, rect.width, self.HEADER_H)
        pygame.draw.rect(surface, ACCENT, header_r)
        draw_text(surface, "Players", self.fonts["md"], WHITE,
                  rect.centerx, header_r.centery, anchor="center")

        y = rect.y + self.HEADER_H + 4

        for i, p in enumerate(self.players):
            if y + self.ROW_H > rect.bottom:
                break

            row_r = pygame.Rect(rect.x + 4, y, rect.width - 8, self.ROW_H - 4)

            # highlight drawing player
            if p.get("is_drawing"):
                pygame.draw.rect(surface, _DRAW_HL, row_r, border_radius=6)

            # avatar — pfp image if available, else coloured circle
            cx = rect.x + 12 + self.AVATAR_R
            cy = y + self.ROW_H // 2
            pfp = get_pfp(p.get("pfp_idx", -1), self.AVATAR_R)
            if pfp is not None:
                pygame.draw.circle(surface, ACCENT, (cx, cy), self.AVATAR_R + 2)
                surface.blit(pfp, pfp.get_rect(center=(cx, cy)))
            else:
                av_color = AVATAR_COLORS[i % len(AVATAR_COLORS)]
                pygame.draw.circle(surface, av_color, (cx, cy), self.AVATAR_R)
                initial = p["name"][0].upper() if p["name"] else "?"
                draw_text(surface, initial, self.fonts["md"], WHITE, cx, cy, anchor="center")

            # name
            name_x = cx + self.AVATAR_R + 8
            draw_text(surface, p["name"][:12], self.fonts["sm"], _NAME_COL,
                      name_x, cy - 10, anchor="midleft")

            # score
            draw_text(surface, str(p["score"]), self.fonts["sm"], _SCORE_COL,
                      name_x, cy + 8, anchor="midleft")

            # pencil icon for current drawer
            if p.get("is_drawing"):
                draw_text(surface, "✏", self.fonts["sm"], ACCENT,
                          row_r.right - 6, cy, anchor="midright")

            y += self.ROW_H
