import pygame
from client.utils import BORDER, CORRECT, WHITE, draw_text, draw_panel_alpha
from client.components.input_box import InputBox

COLOR_NORMAL  = (215, 230, 255)  # light blue-white — unguessed chat
COLOR_GUESSED = ( 34, 160,  74)  # green  — already-guessed player chat
COLOR_SYSTEM  = (155, 180, 215)  # muted blue-grey  — system notices
COLOR_LEAVE   = (200,  60,  60)  # red    — player left
AVATAR_R      = 7
AVATAR_W      = 20
MAX_MESSAGES  = 80


# Derive a consistent accent color for a player name from its hash.
def _name_color(name: str) -> tuple:
    h = abs(hash(name))
    return (max(80, (h >> 16) & 0xFF),
            max(80, (h >>  8) & 0xFF),
            max(80,  h        & 0xFF))


# Break a text string into lines that fit within max_w pixels using the given font.
def _wrap(font, text: str, max_w: int) -> list[str]:
    words, row, rows = text.split(" "), "", []
    for w in words:
        candidate = (row + " " + w).lstrip()
        if font.size(candidate)[0] <= max_w:
            row = candidate
        else:
            if row:
                rows.append(row)
            row = w
    if row:
        rows.append(row)
    return rows or [""]


class ChatBox:
    """Scrollable chat log + guess input.

    Each stored message: {"sender": str, "text": str, "guessed": bool, "system": bool}
    """

    # Initialize the chat with empty message list, zero scroll, and no bound rect.
    def __init__(self, fonts: dict, is_drawing: bool = False):
        self.fonts       = fonts
        self.is_drawing  = is_drawing
        self.has_guessed = False        # has the LOCAL player guessed this round?
        self._messages: list[dict] = []
        self._scroll     = 0
        self._input: InputBox | None   = None
        self._rect: pygame.Rect | None = None

    # Bind the chat to a screen rect and create the guess input box at the bottom.
    def set_rect(self, rect: pygame.Rect):
        self._rect = rect
        input_rect = pygame.Rect(rect.x + 8, rect.bottom - 52, rect.width - 16, 44)
        self._input = InputBox(input_rect, self.fonts["md"],
                               placeholder="Guess the word…", max_len=60)

    # ── Public API ────────────────────────────────────────────────────────────

    # Append a regular chat message and reset scroll to show the newest message.
    def add_message(self, sender: str, text: str, guessed: bool = False):
        self._messages.append({"sender": sender, "text": text,
                                "guessed": guessed, "system": False})
        if len(self._messages) > MAX_MESSAGES:
            self._messages.pop(0)
        self._scroll = 0

    # Append a system notice with an optional custom color and reset scroll.
    def add_system(self, text: str, color=None):
        self._messages.append({"sender": "", "text": text,
                                "guessed": False, "system": True,
                                "color": color or COLOR_SYSTEM})
        if len(self._messages) > MAX_MESSAGES:
            self._messages.pop(0)
        self._scroll = 0

    def handle_event(self, event) -> str | None:
        """Return submitted guess text on Enter, else None."""
        if self.is_drawing or self._input is None:
            return None
        result = self._input.handle_event(event)
        if result is not None:
            self._input.text = ""
            return result.strip() or None
        if (event.type == pygame.MOUSEWHEEL
                and self._rect
                and self._rect.collidepoint(pygame.mouse.get_pos())):
            self._scroll = max(0, self._scroll - event.y * 20)
        return None

    # Tick the input box and update the placeholder text based on whether the player has guessed.
    def update(self, dt_ms: int):
        if self._input:
            self._input.placeholder = (
                "Chat with guessers…" if self.has_guessed else "Guess the word…"
            )
            self._input.update(dt_ms)

    # ── Render ────────────────────────────────────────────────────────────────

    # Draw the scrollable message log and the guess input box (or a drawing label for drawers).
    def render(self, surface: pygame.Surface):
        if not self._rect:
            return
        rect = self._rect

        draw_panel_alpha(surface, rect,
                         bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 60), radius=0)

        INPUT_ZONE = 60   # height reserved at bottom for input
        log_rect   = pygame.Rect(rect.x, rect.y, rect.width, rect.height - INPUT_ZONE)

        clip = surface.get_clip()
        surface.set_clip(log_rect)

        font       = self.fonts["sm"]
        line_h     = font.get_linesize() + 4
        pad        = 8
        text_x     = rect.x + pad + AVATAR_W
        max_text_w = rect.width - pad - AVATAR_W - pad

        # Build flat line list bottom-up.
        # Each entry: (text, color, show_avatar, sender)
        lines: list[tuple] = []
        for msg in reversed(self._messages):
            if msg["system"]:
                color = msg.get("color") or COLOR_SYSTEM
            elif msg["guessed"]:
                color = COLOR_GUESSED
            else:
                color = COLOR_NORMAL

            display = (f"{msg['sender']}: {msg['text']}"
                       if msg["sender"] else msg["text"])
            rows = _wrap(font, display, max_text_w)

            for i, row in enumerate(reversed(rows)):
                is_first = (i == len(rows) - 1)
                lines.append((row, color, is_first and bool(msg["sender"]), msg["sender"]))

        total_h      = len(lines) * line_h
        max_scroll   = max(0, total_h - log_rect.height + pad)
        self._scroll = min(self._scroll, max_scroll)

        y_bot = log_rect.bottom - pad + self._scroll
        for text_line, color, show_avatar, sender in lines:
            y = y_bot - line_h
            if y + line_h >= log_rect.top:
                if show_avatar:
                    pygame.draw.circle(surface, _name_color(sender),
                                       (rect.x + pad + AVATAR_R, y + line_h // 2), AVATAR_R)
                surf = font.render(text_line, True, color)
                surface.blit(surf, (text_x, y))
            y_bot -= line_h
            if y_bot < log_rect.top - line_h:
                break

        surface.set_clip(clip)
        pygame.draw.line(surface, BORDER,
                         (rect.x, log_rect.bottom), (rect.right, log_rect.bottom), 1)

        if not self.is_drawing and self._input:
            self._input.draw(surface)
        elif self.is_drawing:
            surf = self.fonts["sm"].render("You are drawing!", True, COLOR_SYSTEM)
            surface.blit(surf, surf.get_rect(centerx=rect.centerx,
                                             centery=rect.bottom - INPUT_ZONE // 2))
