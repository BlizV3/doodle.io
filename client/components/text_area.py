# -*- coding: utf-8 -*-
import pygame
from client.utils import WHITE, BORDER, ACCENT, TEXT_DARK


class TextArea:
    """Simple multi-line text input — used for custom word lists."""

    # Initialize the multi-line input with its rect, font, placeholder, and cursor blink state.
    def __init__(self, rect, font: pygame.font.Font,
                 placeholder: str = "", max_chars: int = 2000):
        self.rect        = pygame.Rect(rect)
        self.font        = font
        self.placeholder = placeholder
        self.text        = ""
        self.active      = False
        self.max_chars   = max_chars
        self._cursor_ms  = 0
        self._show_cur   = True

    # Handle mouse clicks to activate, backspace, Enter (inserts newline), and typed characters.
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if len(self.text) < self.max_chars:
                    self.text += "\n"
            elif event.unicode and len(self.text) < self.max_chars:
                self.text += event.unicode

    # Advance the cursor blink timer and toggle visibility every 530 ms.
    def update(self, dt_ms: int):
        self._cursor_ms += dt_ms
        if self._cursor_ms >= 530:
            self._cursor_ms = 0
            self._show_cur  = not self._show_cur

    # Break text into display lines that fit within max_w pixels, preserving paragraph breaks.
    def _wrap_lines(self, text: str, max_w: int) -> list[str]:
        result = []
        for paragraph in text.split("\n"):
            if not paragraph:
                result.append("")
                continue
            words, row = paragraph.split(" "), ""
            for word in words:
                candidate = (row + " " + word).lstrip()
                if self.font.size(candidate)[0] <= max_w:
                    row = candidate
                else:
                    if row:
                        result.append(row)
                    row = word
            result.append(row)
        return result

    # Render the text area: background, border, visible wrapped lines or placeholder, and cursor.
    def draw(self, surface: pygame.Surface, enabled: bool = True):
        if enabled:
            bg_col     = WHITE
            border_col = ACCENT if self.active else BORDER
            text_col   = TEXT_DARK
            ph_col     = (180, 185, 190)
        else:
            bg_col     = (210, 212, 218)
            border_col = (170, 174, 182)
            text_col   = (140, 145, 155)
            ph_col     = (160, 163, 170)

        pygame.draw.rect(surface, bg_col, self.rect, border_radius=6)
        pygame.draw.rect(surface, border_col, self.rect, 2, border_radius=6)

        pad    = 10
        line_h = self.font.get_linesize() + 2
        max_w  = self.rect.width  - pad * 2
        max_lines = max(1, (self.rect.height - pad * 2) // line_h)

        clip = surface.get_clip()
        surface.set_clip(self.rect.inflate(-4, -4))

        if not self.text:
            surf = self.font.render(self.placeholder, True, ph_col)
            surface.blit(surf, (self.rect.x + pad, self.rect.y + pad))
        else:
            lines   = self._wrap_lines(self.text, max_w)
            visible = lines[-max_lines:]
            y = self.rect.y + pad
            for line in visible:
                surf = self.font.render(line, True, text_col)
                surface.blit(surf, (self.rect.x + pad, y))
                y += line_h

            if enabled and self.active and self._show_cur:
                last = visible[-1] if visible else ""
                last_y = self.rect.y + pad + (len(visible) - 1) * line_h
                cx = self.rect.x + pad + self.font.size(last)[0] + 1
                pygame.draw.line(surface, TEXT_DARK,
                                 (cx, last_y + 2), (cx, last_y + line_h - 2), 2)

        surface.set_clip(clip)

    def get_words(self) -> list[str]:
        """Parse comma- and newline-separated words, strip whitespace."""
        raw = self.text.replace("\n", ",")
        return [w.strip() for w in raw.split(",") if w.strip()]
