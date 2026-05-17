# -*- coding: utf-8 -*-
import os
import random
import string
import pygame
import client.sounds as sounds
from client.utils import (
    WHITE, BTN_ORANGE, BTN_ORANGE_DARK,
    draw_text, draw_panel_alpha, get_background,
)
from client.components.text_area import TextArea
from client.components.input_box import InputBox

W, H = 1280, 720

_ASSETS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))


# Load an asset image and scale it to the given square size.
def _load_icon(name: str, size: int) -> pygame.Surface:
    path = os.path.join(_ASSETS_DIR, name)
    img  = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))

# generate a random code (mainly for rooms)
def _random_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# (key, label, min, max, step, default, unit)
_SETTINGS = [
    ("max_players", "Players",      2,  10,  1,  6, ""),
    ("draw_time",   "Draw Time",   15, 300, 15, 80, "s"),
    ("rounds",      "Rounds",       1,  10,  1,  3, ""),
    ("word_count",  "Word Options", 1,   5,  1,  3, ""),
    ("hints",       "Hints",        0,   5,  1,  2, ""),
]

# Layout
_ROW_H   = 52
_ROW_Y0  = 88
_LABEL_X = 380
_MINUS_X = 736
_VAL_CX  = 820
_PLUS_X  = 880
_BTN_SZ  = 40
_PANEL_X = 340
_PANEL_W = 600

# Fixed vertical positions (derived from the row layout)
_CODE_INPUT_Y = 452   # below room-code-enable toggle row
_CW_LABEL_Y   = 498
_TEXTAREA_Y   = 512
_TEXTAREA_H   = 100
_CREATE_BTN_Y = 626


class CreateRoomScreen:
    # Build all setting rows, input boxes, toggle buttons, and the back icon.
    def __init__(self, fonts: dict):
        self.fonts      = fonts
        self.error      = ""
        self._back_icon = _load_icon("back.png", 28)
        self._back_btn  = pygame.Rect(24, 24, 42, 42)

        self._values = {s[0]: s[5] for s in _SETTINGS}
        self._custom_words      = False
        self._room_code_enabled = False

        # Room name input (top row)
        self._name_box = InputBox(
            pygame.Rect(490, 40, _PANEL_X + _PANEL_W - 490 - 10, 34),
            fonts["md"], placeholder="My Room", max_len=30,
        )

        # Custom words textarea
        self._word_area = TextArea(
            pygame.Rect(_PANEL_X, _TEXTAREA_Y, _PANEL_W, _TEXTAREA_H),
            fonts["md"],
            placeholder="apple, cat, rocket, house, …",
            max_chars=2000,
        )

        # Room code input + randomizer button
        _code_iw = _PANEL_W - 86
        self._code_box = InputBox(
            pygame.Rect(_PANEL_X, _CODE_INPUT_Y, _code_iw, 36),
            fonts["md"], placeholder="A3F9K2", max_len=16,
        )
        self._randomize_btn = pygame.Rect(_PANEL_X + _code_iw + 6, _CODE_INPUT_Y, 74, 36)

        self._hovered: str | None = None

    # ── layout helpers ────────────────────────────────────────────────────────

    def _row_cy(self, idx: int) -> int:
        return _ROW_Y0 + idx * _ROW_H + _ROW_H // 2

    def _minus_r(self, idx: int) -> pygame.Rect:
        return pygame.Rect(_MINUS_X, self._row_cy(idx) - _BTN_SZ // 2, _BTN_SZ, _BTN_SZ)

    def _plus_r(self, idx: int) -> pygame.Rect:
        return pygame.Rect(_PLUS_X, self._row_cy(idx) - _BTN_SZ // 2, _BTN_SZ, _BTN_SZ)

    # Return the bounding rect for the custom-words ON/OFF toggle button.
    def _toggle_r(self) -> pygame.Rect:
        cy = self._row_cy(len(_SETTINGS))
        return pygame.Rect(_MINUS_X, cy - 22, _PLUS_X + _BTN_SZ - _MINUS_X, 44)

    # Return the bounding rect for the room-code ON/OFF toggle button.
    def _code_toggle_r(self) -> pygame.Rect:
        cy = self._row_cy(len(_SETTINGS) + 1)
        return pygame.Rect(_MINUS_X, cy - 22, _PLUS_X + _BTN_SZ - _MINUS_X, 44)

    @property
    def _create_btn(self) -> pygame.Rect:
        return pygame.Rect(W // 2 - 110, _CREATE_BTN_Y, 220, 52)

    # ── events ────────────────────────────────────────────────────────────────

    # Route input to the name box, word area, code box, or setting increment/decrement buttons.
    def handle_event(self, event) -> dict | None:
        self._name_box.handle_event(event)
        if self._custom_words:
            self._word_area.handle_event(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._word_area.active = False

        if self._room_code_enabled:
            self._code_box.handle_event(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._code_box.active = False

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        pos = event.pos

        if self._back_btn.collidepoint(pos):
            sounds.play("click")
            return {"action": "back"}

        if self._create_btn.collidepoint(pos):
            sounds.play("click")
            return self._build_result()

        # Custom words toggle
        if self._toggle_r().collidepoint(pos):
            sounds.play("click")
            self._custom_words = not self._custom_words
            if not self._custom_words:
                self._word_area.active = False
            return None

        # Room code toggle
        if self._code_toggle_r().collidepoint(pos):
            sounds.play("click")
            self._room_code_enabled = not self._room_code_enabled
            if self._room_code_enabled and not self._code_box.text:
                self._code_box.text = _random_code()
            if not self._room_code_enabled:
                self._code_box.active = False
            return None

        # Randomizer button
        if self._room_code_enabled and self._randomize_btn.collidepoint(pos):
            sounds.play("click")
            self._code_box.text = _random_code()
            return None

        for i, (key, _lbl, mn, mx, step, _def, _unit) in enumerate(_SETTINGS):
            if self._minus_r(i).collidepoint(pos):
                sounds.play("click")
                self._values[key] = max(mn, self._values[key] - step)
            elif self._plus_r(i).collidepoint(pos):
                sounds.play("click")
                self._values[key] = min(mx, self._values[key] + step)

        return None

    # Collect current settings into a dict and return a create action.
    def _build_result(self) -> dict:
        s = dict(self._values)
        s["room_name"] = self._name_box.text.strip() or "My Room"

        word_list = self._word_area.get_words() if self._custom_words else []
        s["custom_words"] = self._custom_words and len(word_list) > 0
        s["word_list"]    = word_list

        code = self._code_box.text.strip().upper() if self._room_code_enabled else ""
        s["room_code"] = code
        return {"action": "create", "settings": s}

    # Tick all text input boxes so cursor blinking stays alive.
    def update(self, dt_ms: int):
        self._name_box.update(dt_ms)
        self._word_area.update(dt_ms)
        self._code_box.update(dt_ms)

    # ── render ────────────────────────────────────────────────────────────────

    # Draw the room settings screen with all rows, toggles, inputs, and the Create button.
    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        draw_text(surface, "Create a Room", self.fonts["xl"], WHITE,
                  W // 2, 16, anchor="center")

        mx, my = pygame.mouse.get_pos()

        # Back button
        back_col = (18, 36, 90, 60) if self._back_btn.collidepoint(mx, my) else (10, 22, 60, 38)
        draw_panel_alpha(surface, self._back_btn, bg_rgba=back_col,
                         border_rgba=(80, 140, 255, 80), radius=10)
        surface.blit(self._back_icon,
                     self._back_icon.get_rect(center=self._back_btn.center))

        # Room name row
        name_row = pygame.Rect(_PANEL_X, 36, _PANEL_W, 42)
        draw_panel_alpha(surface, name_row, bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 30), radius=8)
        draw_text(surface, "Room Name", self.fonts["btn_sm"], (210, 235, 255),
                  _LABEL_X, name_row.centery, anchor="midleft")
        self._name_box.draw(surface)

        # Numeric setting rows
        for i, (key, label, mn, mxv, step, _def, unit) in enumerate(_SETTINGS):
            cy   = self._row_cy(i)
            row  = pygame.Rect(_PANEL_X, cy - _ROW_H // 2, _PANEL_W, _ROW_H)
            draw_panel_alpha(surface, row, bg_rgba=(10, 22, 60, 38),
                             border_rgba=(80, 140, 255, 30), radius=8)

            draw_text(surface, label, self.fonts["btn_md"], (210, 235, 255),
                      _LABEL_X, cy, anchor="midleft")

            val = self._values[key]
            draw_text(surface, f"{val}{unit}", self.fonts["btn_md"], WHITE,
                      _VAL_CX, cy, anchor="center")

            mr = self._minus_r(i)
            can_dec = val > mn
            mc = BTN_ORANGE_DARK if (mr.collidepoint(mx, my) and can_dec) else \
                 (BTN_ORANGE if can_dec else (70, 70, 90))
            pygame.draw.rect(surface, mc, mr, border_radius=8)
            draw_text(surface, "-", self.fonts["btn_lg"], WHITE,
                      mr.centerx, mr.centery, anchor="center")

            pr = self._plus_r(i)
            can_inc = val < mxv
            pc = BTN_ORANGE_DARK if (pr.collidepoint(mx, my) and can_inc) else \
                 (BTN_ORANGE if can_inc else (70, 70, 90))
            pygame.draw.rect(surface, pc, pr, border_radius=8)
            draw_text(surface, "+", self.fonts["btn_lg"], WHITE,
                      pr.centerx, pr.centery, anchor="center")

        # Custom Words toggle row
        ci  = len(_SETTINGS)
        cy  = self._row_cy(ci)
        row = pygame.Rect(_PANEL_X, cy - _ROW_H // 2, _PANEL_W, _ROW_H)
        draw_panel_alpha(surface, row, bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 30), radius=8)
        draw_text(surface, "Custom Words", self.fonts["btn_md"], (210, 235, 255),
                  _LABEL_X, cy, anchor="midleft")
        tr = self._toggle_r()
        if self._custom_words:
            tc = (28, 140, 60) if tr.collidepoint(mx, my) else (22, 110, 48)
            tl = "ON"
        else:
            tc = (130, 40, 40) if tr.collidepoint(mx, my) else (100, 28, 28)
            tl = "OFF"
        pygame.draw.rect(surface, tc, tr, border_radius=10)
        draw_text(surface, tl, self.fonts["btn_md"], WHITE,
                  tr.centerx, tr.centery, anchor="center")

        # Room Code toggle row
        rci = len(_SETTINGS) + 1
        rcy = self._row_cy(rci)
        rrow = pygame.Rect(_PANEL_X, rcy - _ROW_H // 2, _PANEL_W, _ROW_H)
        draw_panel_alpha(surface, rrow, bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 30), radius=8)
        draw_text(surface, "Room Code", self.fonts["btn_md"], (210, 235, 255),
                  _LABEL_X, rcy, anchor="midleft")
        ctr = self._code_toggle_r()
        if self._room_code_enabled:
            ctc = (28, 140, 60) if ctr.collidepoint(mx, my) else (22, 110, 48)
            ctl = "ON"
        else:
            ctc = (130, 40, 40) if ctr.collidepoint(mx, my) else (100, 28, 28)
            ctl = "OFF"
        pygame.draw.rect(surface, ctc, ctr, border_radius=10)
        draw_text(surface, ctl, self.fonts["btn_md"], WHITE,
                  ctr.centerx, ctr.centery, anchor="center")

        # Room code input + randomizer (always visible, greyed when disabled)
        lbl_col = (210, 235, 255) if self._room_code_enabled else (140, 148, 165)
        draw_text(surface, "Code:", self.fonts["sm"], lbl_col,
                  _LABEL_X, _CODE_INPUT_Y + 18, anchor="midleft")
        self._code_box.draw(surface, enabled=self._room_code_enabled)
        if self._room_code_enabled:
            rc = BTN_ORANGE_DARK if self._randomize_btn.collidepoint(mx, my) else BTN_ORANGE
        else:
            rc = (90, 90, 110)
        pygame.draw.rect(surface, rc, self._randomize_btn, border_radius=8)
        draw_text(surface, "Random", self.fonts["sm"], WHITE,
                  self._randomize_btn.centerx, self._randomize_btn.centery, anchor="center")

        # Custom words textarea (always visible, greyed when disabled)
        lbl_cw = (210, 235, 255) if self._custom_words else (140, 148, 165)
        draw_text(surface, "Words (comma or newline separated):",
                  self.fonts["sm"], lbl_cw, _PANEL_X, _CW_LABEL_Y, anchor="midleft")
        self._word_area.draw(surface, enabled=self._custom_words)

        # Create button
        cb  = self._create_btn
        cc  = BTN_ORANGE_DARK if cb.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, cc, cb, border_radius=10)
        draw_text(surface, "Create", self.fonts["lg"], WHITE,
                  cb.centerx, cb.centery, anchor="center")

        if self.error:
            draw_text(surface, self.error, self.fonts["sm"], (220, 60, 60),
                      W // 2, H - 24, anchor="center")

        # Hover sounds
        new_hov: str | None = None
        if self._back_btn.collidepoint(mx, my):             new_hov = "back"
        elif cb.collidepoint(mx, my):                       new_hov = "create"
        elif self._toggle_r().collidepoint(mx, my):         new_hov = "cw_toggle"
        elif self._code_toggle_r().collidepoint(mx, my):    new_hov = "rc_toggle"
        elif self._room_code_enabled and self._randomize_btn.collidepoint(mx, my): new_hov = "rand"
        else:
            for i in range(len(_SETTINGS)):
                if self._minus_r(i).collidepoint(mx, my): new_hov = f"m{i}"; break
                if self._plus_r(i).collidepoint(mx, my):  new_hov = f"p{i}"; break
        if new_hov != self._hovered:
            self._hovered = new_hov
            if new_hov:
                sounds.play("hover")
