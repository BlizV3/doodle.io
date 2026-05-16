import pygame
from client.utils import (
    BG, WHITE, ACCENT, ACCENT_DARK, TEXT_DARK, TEXT_MID, BORDER,
    gradient_rect, draw_text, draw_panel, HEADER_A, HEADER_B,
)
from client.components.input_box import InputBox

W, H = 1280, 720


class LobbyScreen:
    """Name + server address entry, then click Play."""

    def __init__(self, fonts: dict):
        self.fonts = fonts
        self.error = ""

        cx = W // 2

        self._name_box = InputBox(
            pygame.Rect(cx - 180, 300, 360, 48),
            fonts["md"], placeholder="Enter your name…", max_len=20,
        )
        self._host_box = InputBox(
            pygame.Rect(cx - 180, 380, 260, 48),
            fonts["md"], placeholder="Host (localhost)", max_len=64,
        )
        self._port_box = InputBox(
            pygame.Rect(cx + 90, 380, 90, 48),
            fonts["md"], placeholder="5555", max_len=5,
        )
        self._play_btn = pygame.Rect(cx - 100, 460, 200, 54)

        self._name_box.active = True

    def handle_event(self, event) -> dict | None:
        self._name_box.handle_event(event)
        self._host_box.handle_event(event)
        self._port_box.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._play_btn.collidepoint(event.pos):
                return self._build_connect()

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._build_connect()

        return None

    def _build_connect(self) -> dict | None:
        name = self._name_box.text.strip()
        if not name:
            self.error = "Please enter your name."
            return None
        host = self._host_box.text.strip() or "localhost"
        try:
            port = int(self._port_box.text.strip() or "5555")
        except ValueError:
            self.error = "Invalid port number."
            return None
        self.error = ""
        return {"action": "connect", "name": name, "host": host, "port": port}

    def update(self, dt_ms: int):
        self._name_box.update(dt_ms)
        self._host_box.update(dt_ms)
        self._port_box.update(dt_ms)

    def render(self, surface: pygame.Surface):
        surface.fill(BG)

        # top decorative bar
        gradient_rect(surface, pygame.Rect(0, 0, W, 8), HEADER_A, HEADER_B)

        # logo
        logo_surf = self.fonts["logo"].render("doodle", True, ACCENT)
        io_surf   = self.fonts["logo"].render(".io", True, HEADER_A)
        lx = W // 2 - (logo_surf.get_width() + io_surf.get_width()) // 2
        surface.blit(logo_surf, (lx, 80))
        surface.blit(io_surf,   (lx + logo_surf.get_width(), 80))

        draw_text(surface, "Draw. Guess. Win.", self.fonts["md"], TEXT_MID,
                  W // 2, 160, anchor="center")

        # card
        card = pygame.Rect(W // 2 - 220, 260, 440, 300)
        draw_panel(surface, card, bg=WHITE, radius=12)

        draw_text(surface, "Your Name", self.fonts["sm"], TEXT_MID,
                  W // 2 - 180, 285, anchor="midleft")
        self._name_box.draw(surface)

        draw_text(surface, "Server", self.fonts["sm"], TEXT_MID,
                  W // 2 - 180, 365, anchor="midleft")
        self._host_box.draw(surface)
        self._port_box.draw(surface)

        # play button
        mx, my = pygame.mouse.get_pos()
        btn_col = ACCENT_DARK if self._play_btn.collidepoint(mx, my) else ACCENT
        pygame.draw.rect(surface, btn_col, self._play_btn, border_radius=10)
        draw_text(surface, "Play!", self.fonts["lg"], WHITE,
                  self._play_btn.centerx, self._play_btn.centery, anchor="center")

        if self.error:
            draw_text(surface, self.error, self.fonts["sm"], (220, 60, 60),
                      W // 2, 530, anchor="center")
