import pygame
from client.utils import BORDER, ACCENT, TEXT_DARK, WHITE


class InputBox:
    # Initialize the input box with its rect, font, placeholder, and cursor blink state.
    def __init__(self, rect, font: pygame.font.Font,
                 placeholder: str = "", max_len: int = 48):
        self.rect        = pygame.Rect(rect)
        self.font        = font
        self.placeholder = placeholder
        self.max_len     = max_len
        self.text        = ""
        self.active      = False
        self._cursor_ms  = 0
        self._show_cur   = True

    def handle_event(self, event) -> str | None:
        """Return submitted text on RETURN, else None."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                submitted = self.text
                return submitted
            elif event.unicode and len(self.text) < self.max_len:
                self.text += event.unicode
        return None

    # Advance the cursor blink timer and toggle visibility every 530 ms.
    def update(self, dt_ms: int):
        self._cursor_ms += dt_ms
        if self._cursor_ms >= 530:
            self._cursor_ms = 0
            self._show_cur  = not self._show_cur

    # Render the input field: background, border, text or placeholder, and blinking cursor.
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

        pad = 10
        if self.text:
            surf = self.font.render(self.text, True, text_col)
        else:
            surf = self.font.render(self.placeholder, True, ph_col)

        cy = self.rect.y + (self.rect.height - surf.get_height()) // 2
        surface.blit(surf, (self.rect.x + pad, cy))

        if enabled and self.active and self._show_cur:
            cx = self.rect.x + pad + self.font.size(self.text)[0] + 1
            pygame.draw.line(surface, TEXT_DARK,
                             (cx, self.rect.y + 6),
                             (cx, self.rect.y + self.rect.height - 6), 2)
