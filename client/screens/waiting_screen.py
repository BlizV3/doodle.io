import os
import pygame
import client.sounds as sounds
from client.utils import (
    WHITE, ACCENT, TEXT_DARK, TEXT_MID,
    BTN_ORANGE, BTN_ORANGE_DARK,
    AVATAR_COLORS, draw_text, draw_panel, draw_panel_alpha, get_background,
)
from client.pfp import get_pfp

W, H = 1280, 720

_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets")
)

def _load_icon(name: str, size: int) -> pygame.Surface:
    path = os.path.join(_ASSETS_DIR, name)
    img  = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))


_RED        = (200,  50,  50)
_RED_DARK   = (160,  30,  30)
_GRAY       = (140, 148, 160)
_GRAY_DARK  = (100, 108, 118)

# Square icon-button size (+10 % over 48 → 53)
_SQ = 53
# Start button size (+10 % over 220×48 → 242×53)
_START_W, _START_H = 242, 53
_BTN_Y = H - 68


class WaitingScreen:
    """Lobby waiting room — shown after connecting until the game starts."""

    _CARD_W = 170
    _CARD_H = 108
    _KICK_W =  26

    def __init__(self, fonts: dict, local_name: str):
        self.fonts       = fonts
        self.local_name  = local_name
        self.players: list[dict] = []
        self.status_msg  = "Waiting for players…"
        self._is_owner   = False
        self._confirm    = False        # close-room confirmation
        self._leave_confirm = False     # leave-room confirmation
        self.max_players = 6
        self.room_code   = ""
        self.room_name   = ""

        self._kick_rects: dict[str, pygame.Rect] = {}
        self._hovered: str | None = None

        # bottom-bar buttons
        self._leave_btn = pygame.Rect(W - 20 - _SQ,              _BTN_Y, _SQ, _SQ)
        self._close_btn = pygame.Rect(W - 20 - _SQ - 16 - _SQ,  _BTN_Y, _SQ, _SQ)
        self._start_btn = pygame.Rect(W // 2 - _START_W // 2,   _BTN_Y, _START_W, _START_H)

        # close-room confirmation dialog
        self._confirm_yes = pygame.Rect(W // 2 - 150, H // 2 + 44, 130, 44)
        self._confirm_no  = pygame.Rect(W // 2 +  20, H // 2 + 44, 130, 44)

        # leave-room confirmation dialog
        self._leave_yes = pygame.Rect(W // 2 - 150, H // 2 + 44, 130, 44)
        self._leave_no  = pygame.Rect(W // 2 +  20, H // 2 + 44, 130, 44)

        # icons (slightly larger for the bigger square buttons)
        self._leave_icon = _load_icon("leave.png", 32)
        self._trash_icon = _load_icon("trash.png", 28)

    # ── public API ────────────────────────────────────────────────────────────

    def update_players(self, players: list[dict], owner_name: str = "",
                       max_players: int = 6, room_code: str = "",
                       room_name: str = ""):
        self.players     = players
        self.max_players = max_players
        self.room_code   = room_code
        self.room_name   = room_name
        self._is_owner   = bool(owner_name) and (owner_name == self.local_name)
        n = len(players)
        if n < 2:
            self.status_msg = f"Waiting for at least one more player… ({n}/{max_players})"
        else:
            self.status_msg = f"{n}/{max_players} players ready"

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event) -> dict | None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        pos = event.pos

        # Leave confirmation captures all clicks
        if self._leave_confirm:
            if self._leave_yes.collidepoint(pos):
                sounds.play("click")
                self._leave_confirm = False
                return {"action": "leave"}
            if self._leave_no.collidepoint(pos):
                sounds.play("click")
                self._leave_confirm = False
            return None

        # Close-room confirmation captures all clicks
        if self._confirm:
            if self._confirm_yes.collidepoint(pos):
                sounds.play("click")
                self._confirm = False
                return {"action": "close_room"}
            if self._confirm_no.collidepoint(pos):
                sounds.play("click")
                self._confirm = False
            return None

        # Start game button (owner only, 2+ players)
        if self._is_owner and len(self.players) >= 2 and self._start_btn.collidepoint(pos):
            sounds.play("click")
            return {"action": "start_game"}

        # Leave button → show confirmation
        if self._leave_btn.collidepoint(pos):
            sounds.play("click")
            self._leave_confirm = True
            return None

        # Close-room button (owner only) → show confirmation
        if self._is_owner and self._close_btn.collidepoint(pos):
            sounds.play("click")
            self._confirm = True
            return None

        # Kick buttons (owner only)
        if self._is_owner:
            for name, rect in self._kick_rects.items():
                if rect.collidepoint(pos) and name != self.local_name:
                    sounds.play("click")
                    return {"action": "kick", "name": name}

        return None

    def update(self, dt_ms: int):
        pass

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        title = self.room_name or "doodle.io"
        draw_text(surface, title, self.fonts["logo"], WHITE,
                  W // 2, 36, anchor="center")
        draw_text(surface, self.status_msg, self.fonts["md"], (210, 235, 255),
                  W // 2, 116, anchor="center")

        self._draw_player_grid(surface)
        self._draw_bottom_bar(surface)

        if self._confirm:
            self._draw_confirm_dialog(surface)
        elif self._leave_confirm:
            self._draw_leave_confirm_dialog(surface)

        mx, my = pygame.mouse.get_pos()
        new_hov = None
        if self._leave_confirm:
            if self._leave_yes.collidepoint(mx, my):    new_hov = "leave_yes"
            elif self._leave_no.collidepoint(mx, my):   new_hov = "leave_no"
        elif self._confirm:
            if self._confirm_yes.collidepoint(mx, my):  new_hov = "yes"
            elif self._confirm_no.collidepoint(mx, my): new_hov = "no"
        else:
            if self._leave_btn.collidepoint(mx, my):    new_hov = "leave"
            elif self._is_owner and self._close_btn.collidepoint(mx, my): new_hov = "close"
            elif self._is_owner and self._start_btn.collidepoint(mx, my): new_hov = "start"
            else:
                for name, rect in self._kick_rects.items():
                    if rect.collidepoint(mx, my) and name != self.local_name:
                        new_hov = f"kick_{name}"
                        break
        if new_hov != self._hovered:
            self._hovered = new_hov
            if new_hov:
                sounds.play("hover")

    # ── private helpers ───────────────────────────────────────────────────────

    def _draw_player_grid(self, surface: pygame.Surface):
        self._kick_rects.clear()
        cw, ch = self._CARD_W, self._CARD_H
        cols   = max(1, min(len(self.players), 6))
        total  = cols * cw + (cols - 1) * 16
        sx     = W // 2 - total // 2
        y0     = 168

        for i, p in enumerate(self.players):
            col_i = i % cols
            row_i = i // cols
            x     = sx + col_i * (cw + 16)
            cy    = y0 + row_i * (ch + 16)

            card_r = pygame.Rect(x, cy, cw, ch)
            draw_panel_alpha(surface, card_r,
                             bg_rgba=(10, 22, 60, 38),
                             border_rgba=(80, 140, 255, 70), radius=10)

            acx, acy = x + cw // 2, cy + 36
            pfp = get_pfp(p.get("pfp_idx", -1), 22)
            if pfp is not None:
                pygame.draw.circle(surface, ACCENT, (acx, acy), 24)
                surface.blit(pfp, pfp.get_rect(center=(acx, acy)))
            else:
                av_col = AVATAR_COLORS[i % len(AVATAR_COLORS)]
                pygame.draw.circle(surface, av_col, (acx, acy), 22)
                draw_text(surface, p["name"][0].upper(), self.fonts["md"], WHITE,
                          acx, acy, anchor="center")

            name_col = (170, 215, 255) if p["name"] == self.local_name else (210, 235, 255)
            draw_text(surface, p["name"][:14], self.fonts["sm"], name_col,
                      acx, cy + 72, anchor="center")

            if self._is_owner and p["name"] != self.local_name:
                kw = self._KICK_W
                kr = pygame.Rect(card_r.right - kw - 4, card_r.y + 4, kw, kw)
                self._kick_rects[p["name"]] = kr
                mx, my = pygame.mouse.get_pos()
                hov    = kr.collidepoint(mx, my)
                pygame.draw.rect(surface, _RED_DARK if hov else _RED, kr, border_radius=5)
                draw_text(surface, "x", self.fonts["sm"], WHITE,
                          kr.centerx, kr.centery, anchor="center")

    def _draw_bottom_bar(self, surface: pygame.Surface):
        mx, my = pygame.mouse.get_pos()

        # Room code display — bottom-left
        if self.room_code:
            draw_text(surface, "ROOM CODE", self.fonts["sm"], (130, 155, 195),
                      20, _BTN_Y - 2, anchor="topleft")
            draw_text(surface, self.room_code, self.fonts["btn_lg"], (210, 240, 255),
                      20, _BTN_Y + 18, anchor="topleft")

        # Leave button (square, icon only)
        self._draw_sq_btn(surface, self._leave_btn, self._leave_icon,
                          (200, 80, 40, 200), (160, 52, 18, 220), mx, my)

        # Owner-only buttons
        if self._is_owner:
            # Close Room button (square, icon only)
            self._draw_sq_btn(surface, self._close_btn, self._trash_icon,
                              (*_RED, 200), (*_RED_DARK, 220), mx, my)

            # Start Game button
            can_start = len(self.players) >= 2
            sc = BTN_ORANGE_DARK if (can_start and self._start_btn.collidepoint(mx, my)) else \
                 (BTN_ORANGE if can_start else (90, 90, 110))
            pygame.draw.rect(surface, sc, self._start_btn, border_radius=12)
            draw_text(surface, "Start Game", self.fonts["btn_md"], WHITE,
                      self._start_btn.centerx, self._start_btn.centery, anchor="center")

    def _draw_sq_btn(self, surface, btn, icon, col_normal, col_hover, mx, my):
        col = col_hover if btn.collidepoint(mx, my) else col_normal
        panel = pygame.Surface((btn.width, btn.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, col, panel.get_rect(), border_radius=12)
        surface.blit(panel, btn.topleft)
        surface.blit(icon, icon.get_rect(center=btn.center))

    def _draw_confirm_dialog(self, surface: pygame.Surface):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 165))
        surface.blit(veil, (0, 0))

        panel_r = pygame.Rect(W // 2 - 230, H // 2 - 110, 460, 210)
        draw_panel(surface, panel_r, bg=WHITE, radius=16)

        draw_text(surface, "Close the room?", self.fonts["lg"], TEXT_DARK,
                  panel_r.centerx, panel_r.y + 32, anchor="center")
        draw_text(surface, "Everyone will be kicked and the server will close.",
                  self.fonts["sm"], TEXT_MID,
                  panel_r.centerx, panel_r.y + 72, anchor="center")

        mx, my = pygame.mouse.get_pos()

        yc = _RED_DARK if self._confirm_yes.collidepoint(mx, my) else _RED
        pygame.draw.rect(surface, yc, self._confirm_yes, border_radius=8)
        draw_text(surface, "Yes, close it", self.fonts["md"], WHITE,
                  self._confirm_yes.centerx, self._confirm_yes.centery, anchor="center")

        cc = _GRAY_DARK if self._confirm_no.collidepoint(mx, my) else _GRAY
        pygame.draw.rect(surface, cc, self._confirm_no, border_radius=8)
        draw_text(surface, "Cancel", self.fonts["md"], WHITE,
                  self._confirm_no.centerx, self._confirm_no.centery, anchor="center")

    def _draw_leave_confirm_dialog(self, surface: pygame.Surface):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 165))
        surface.blit(veil, (0, 0))

        panel_r = pygame.Rect(W // 2 - 230, H // 2 - 110, 460, 210)
        draw_panel(surface, panel_r, bg=WHITE, radius=16)

        draw_text(surface, "Leave the room?", self.fonts["lg"], TEXT_DARK,
                  panel_r.centerx, panel_r.y + 32, anchor="center")
        draw_text(surface, "Are you sure you want to leave?",
                  self.fonts["sm"], TEXT_MID,
                  panel_r.centerx, panel_r.y + 72, anchor="center")

        mx, my = pygame.mouse.get_pos()

        yc = _RED_DARK if self._leave_yes.collidepoint(mx, my) else _RED
        pygame.draw.rect(surface, yc, self._leave_yes, border_radius=8)
        draw_text(surface, "Yes, leave", self.fonts["md"], WHITE,
                  self._leave_yes.centerx, self._leave_yes.centery, anchor="center")

        cc = _GRAY_DARK if self._leave_no.collidepoint(mx, my) else _GRAY
        pygame.draw.rect(surface, cc, self._leave_no, border_radius=8)
        draw_text(surface, "Stay", self.fonts["md"], WHITE,
                  self._leave_no.centerx, self._leave_no.centery, anchor="center")
