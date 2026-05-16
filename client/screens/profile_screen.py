import os
import pygame
from client.utils import (
    WHITE, ACCENT, TEXT_MID,
    BTN_ORANGE, BTN_ORANGE_DARK,
    AVATAR_COLORS, draw_text, get_background,
)
from client.components.input_box import InputBox
import client.sounds as sounds

W, H = 1280, 720
PFP_SIZE = 140   # diameter of the pfp displayed on this screen

from client.pfp import load_pfps as _load_pfps_lib

def _load_pfps(radius: int) -> list[pygame.Surface]:
    return _load_pfps_lib(radius)


def _draw_circle_pfp(surface, cx, cy, idx):
    color = AVATAR_COLORS[idx % len(AVATAR_COLORS)]
    pygame.draw.circle(surface, color, (cx, cy), PFP_SIZE // 2)
    font = pygame.font.Font(None, 52)
    s = font.render(str(idx + 1), True, WHITE)
    surface.blit(s, s.get_rect(center=(cx, cy)))


class ProfileScreen:
    def __init__(self, fonts: dict, name: str = "", pfp_idx: int = 0):
        self.fonts  = fonts
        self.error  = ""
        self._pfps  = _load_pfps(PFP_SIZE // 2)
        self._count = max(len(self._pfps), len(AVATAR_COLORS))
        self._idx   = pfp_idx % max(self._count, 1)

        cx = W // 2
        # Clickable pfp area (140×140 centred at cy=220)
        self._pfp_rect   = pygame.Rect(cx - PFP_SIZE // 2, 220 - PFP_SIZE // 2,
                                       PFP_SIZE, PFP_SIZE)
        self._design_btn = pygame.Rect(cx - 80, 305, 160, 36)
        self._name_box   = InputBox(
            pygame.Rect(cx - 160, 376, 320, 42),
            fonts["md"], placeholder="Enter your name…", max_len=20,
        )
        self._name_box.text   = name
        self._name_box.active = True
        self._accept_btn = pygame.Rect(cx - 110, 434, 220, 54)
        self._hovered: str | None = None

    # ── input ─────────────────────────────────────────────────────────────────

    def handle_event(self, event) -> dict | None:
        self._name_box.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._pfp_rect.collidepoint(event.pos):
                sounds.play("click")
                self._idx = (self._idx + 1) % self._count
            elif self._design_btn.collidepoint(event.pos):
                sounds.play("click")
                return {"action": "design_pfp", "name": self._name_box.text}
            elif self._accept_btn.collidepoint(event.pos):
                sounds.play("click")
                return self._accept()

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._accept()

        return None

    def _accept(self) -> dict | None:
        name = self._name_box.text.strip()
        if not name:
            self.error = "Please enter your name."
            return None
        self.error = ""
        surf = self._pfps[self._idx] if self._idx < len(self._pfps) else None
        return {"action": "profile_done", "name": name, "pfp_idx": self._idx, "pfp_surf": surf}

    def update(self, dt_ms: int):
        self._name_box.update(dt_ms)

    # ── render ─────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        draw_text(surface, "Create your profile", self.fonts["xl"], WHITE,
                  W // 2, 36, anchor="center")

        cx, cy = W // 2, 220

        # pfp ring
        pygame.draw.circle(surface, ACCENT, (cx, cy), PFP_SIZE // 2 + 5)
        if self._idx < len(self._pfps):
            surface.blit(self._pfps[self._idx],
                         self._pfps[self._idx].get_rect(center=(cx, cy)))
        else:
            _draw_circle_pfp(surface, cx, cy, self._idx)

        # hover highlight on pfp
        mx, my = pygame.mouse.get_pos()
        if self._pfp_rect.collidepoint(mx, my):
            ring = pygame.Surface((PFP_SIZE + 10, PFP_SIZE + 10), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 255, 255, 55),
                               (PFP_SIZE // 2 + 5, PFP_SIZE // 2 + 5), PFP_SIZE // 2 + 5)
            surface.blit(ring, (cx - PFP_SIZE // 2 - 5, cy - PFP_SIZE // 2 - 5))

        draw_text(surface, f"{self._idx + 1} / {self._count}", self.fonts["sm"], (210, 235, 255),
                  cx, cy + PFP_SIZE // 2 + 14, anchor="center")

        # Design button
        dc = BTN_ORANGE_DARK if self._design_btn.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, dc, self._design_btn, border_radius=8)
        draw_text(surface, "Design", self.fonts["btn_md"], WHITE,
                  self._design_btn.centerx, self._design_btn.centery, anchor="center")

        # name
        draw_text(surface, "Your Name", self.fonts["sm"], (210, 235, 255),
                  W // 2, 358, anchor="center")
        self._name_box.draw(surface)

        # accept
        col = BTN_ORANGE_DARK if self._accept_btn.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, col, self._accept_btn, border_radius=10)
        draw_text(surface, "Accept", self.fonts["lg"], WHITE,
                  self._accept_btn.centerx, self._accept_btn.centery, anchor="center")

        if self.error:
            draw_text(surface, self.error, self.fonts["sm"], (220, 60, 60),
                      W // 2, 500, anchor="center")

        new_hov = None
        if self._accept_btn.collidepoint(mx, my):   new_hov = "accept"
        elif self._design_btn.collidepoint(mx, my):  new_hov = "design"
        elif self._pfp_rect.collidepoint(mx, my):    new_hov = "pfp"
        if new_hov != self._hovered:
            self._hovered = new_hov
            if new_hov:
                sounds.play("hover")
