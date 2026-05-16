import pygame
from shared.protocol import (
    DRAW, DRAW_FILL, DRAW_CLEAR, DRAW_SNAPSHOT,
    PLAYER_LIST, ROUND_START, CHOOSE_WORD, WORD_CHOSEN,
    HINT_UPDATE, TIMER_UPDATE, CHAT_MSG, ROUND_END, GAME_END,
)
from client.components.toolbar import TOOL_EYEDROPPER, TOOL_BRUSH, TOOL_FILL
import client.sounds as sounds
from client.utils import (
    WHITE, ACCENT, TEXT_DARK, TEXT_MID,
    BTN_ORANGE, BTN_ORANGE_DARK,
    draw_text, draw_panel, get_background,
)
from client.components.canvas    import DrawingCanvas
from client.components.toolbar   import Toolbar
from client.components.chat_box  import ChatBox
from client.components.hud       import HUD
from client.components.scoreboard import Scoreboard

W, H = 1280, 720

# Layout constants
HUD_H       = 80
LEFT_W      = 220
RIGHT_W     = 280
TOOLBAR_H   = 72
CANVAS_X    = LEFT_W
CANVAS_Y    = HUD_H
CANVAS_W    = W - LEFT_W - RIGHT_W
CANVAS_H    = H - HUD_H - TOOLBAR_H


class GameScreen:
    def __init__(self, fonts: dict, local_name: str):
        self.fonts      = fonts
        self.local_name = local_name

        self.hud        = HUD(fonts, height=HUD_H)
        self.scoreboard = Scoreboard(fonts)
        self.canvas     = DrawingCanvas(CANVAS_W, CANVAS_H)
        self.toolbar    = Toolbar(fonts)
        self.chat       = ChatBox(fonts, is_drawing=False)

        self.chat.set_rect(pygame.Rect(W - RIGHT_W, HUD_H, RIGHT_W, H - HUD_H))

        # rects used for layout
        self._hud_rect      = pygame.Rect(0,       0,      W,       HUD_H)
        self._sb_rect       = pygame.Rect(0,       HUD_H,  LEFT_W,  H - HUD_H)
        self._canvas_rect   = pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)
        self._toolbar_rect  = pygame.Rect(CANVAS_X, CANVAS_Y + CANVAS_H, CANVAS_W, TOOLBAR_H)

        self._has_guessed = False

        # overlay state
        self._show_word_choice = False
        self._word_choices: list[str] = []
        self._round_end_overlay: dict | None = None  # {word, scores, timer}
        self._round_end_ms = 0
        self._game_end: list[dict] | None = None  # scores

        self._pending_game_end = False
        self._hovered_word: str | None = None

    # ── Server message routing ────────────────────────────────────────────────

    def update(self, msg: dict) -> str | None:
        """Process one server message. Return 'game_end' if game is over."""
        t = msg.get("type")

        if t == PLAYER_LIST:
            self.scoreboard.update(msg["players"])
            # detect when the local player's has_guessed flips to True
            for p in msg.get("players", []):
                if p["name"] == self.local_name and p.get("has_guessed"):
                    self._has_guessed     = True
                    self.chat.has_guessed = True

        elif t == ROUND_START:
            drawer        = msg["drawer"]
            local_drawing = (drawer == self.local_name)
            self.canvas.active   = local_drawing
            self.canvas.reset()
            self.toolbar.active  = local_drawing
            self.chat.is_drawing = local_drawing
            self.hud.update_round(
                drawer, msg["round"], msg["total_rounds"],
                msg["hint"], msg["time"], local_drawing,
            )
            self._show_word_choice  = False
            self._round_end_overlay = None
            self._has_guessed       = False
            self.chat.has_guessed   = False
            if local_drawing:
                self.chat.add_system(f"— Round {msg['round']}: choose your word! —")
            else:
                self.chat.add_system(f"— Round {msg['round']}: {drawer} is choosing a word… —")

        elif t == CHOOSE_WORD:
            self._word_choices     = msg["words"]
            self._show_word_choice = True

        elif t == WORD_CHOSEN:
            self._show_word_choice = False
            self.chat.add_system(f"{msg['drawer']} chose a word!")

        elif t == HINT_UPDATE:
            self.hud.update_hint(msg["hint"])

        elif t == TIMER_UPDATE:
            self.hud.update_timer(msg["remaining"])

        elif t == DRAW:
            self.canvas.apply_draw(msg)

        elif t == DRAW_FILL:
            self.canvas.apply_fill(msg)

        elif t == DRAW_CLEAR:
            self.canvas.apply_clear()

        elif t == DRAW_SNAPSHOT:
            self.canvas.apply_snapshot(msg["data"])

        elif t == CHAT_MSG:
            if msg.get("sender"):
                self.chat.add_message(msg["sender"], msg["text"],
                                      guessed=msg.get("guessed", False))
            else:
                self.chat.add_system(msg["text"])

        elif t == ROUND_END:
            self._round_end_overlay = {"word": msg["word"], "scores": msg["scores"]}
            self._round_end_ms      = 5000
            self.canvas.active      = False
            self.toolbar.active     = False

        elif t == GAME_END:
            self._game_end = msg["scores"]
            return "game_end"

        return None

    # ── Events → outgoing messages ────────────────────────────────────────────

    def handle_event(self, event) -> list[dict]:
        msgs: list[dict] = []

        # word choice overlay captures all input
        if self._show_word_choice:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                choice = self._hit_word_choice(event.pos)
                if choice:
                    sounds.play("click")
                    from shared.protocol import WORD_CHOICE
                    msgs.append({"type": WORD_CHOICE, "word": choice})
                    self._show_word_choice = False
            return msgs

        # keyboard shortcuts (undo / redo)
        if event.type == pygame.KEYDOWN and self.canvas.active:
            ctrl = event.mod & pygame.KMOD_CTRL
            if ctrl and event.key == pygame.K_z and not (event.mod & pygame.KMOD_SHIFT):
                if self.canvas.undo():
                    msgs.append({"type": DRAW_SNAPSHOT, "data": self.canvas.get_snapshot_b64()})
            elif ctrl and (event.key == pygame.K_y or
                           (event.key == pygame.K_z and event.mod & pygame.KMOD_SHIFT)):
                if self.canvas.redo():
                    msgs.append({"type": DRAW_SNAPSHOT, "data": self.canvas.get_snapshot_b64()})

        # canvas
        canvas_msgs = self.canvas.handle_event(event, self._canvas_rect)
        msgs.extend(canvas_msgs)

        # eyedropper pick: update colour, auto-switch to pencil (before toolbar sync)
        for m in list(msgs):
            if m.get("type") == "eyedropper_pick":
                msgs.remove(m)
                self.toolbar.color = tuple(m["color"])
                self.toolbar.tool  = TOOL_BRUSH

        # toolbar
        if self.toolbar.handle_event(event, self._toolbar_rect):
            msgs.append({"type": DRAW_CLEAR})
            self.canvas.clear()

        # sync toolbar → canvas
        self.canvas.color = self.toolbar.color
        self.canvas.size  = self.toolbar.current_size
        self.canvas.tool  = self.toolbar.tool

        # chat / guess
        guess = self.chat.handle_event(event)
        if guess:
            from shared.protocol import GUESS
            msgs.append({"type": GUESS, "text": guess})

        return msgs

    def tick(self, dt_ms: int):
        self.chat.update(dt_ms)
        if self._round_end_overlay:
            self._round_end_ms -= dt_ms
            if self._round_end_ms <= 0:
                self._round_end_overlay = None

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        self.hud.render(surface, self._hud_rect)
        self.scoreboard.render(surface, self._sb_rect)
        self.canvas.render(surface, CANVAS_X, CANVAS_Y)
        self.toolbar.render(surface, self._toolbar_rect)
        self.chat.render(surface)

        if self._round_end_overlay:
            self._draw_round_end(surface)

        if self._show_word_choice:
            self._draw_word_choice(surface)

        # Brush preview dot
        if self.toolbar.active and self.toolbar.tool == TOOL_BRUSH:
            mx, my = pygame.mouse.get_pos()
            if self._canvas_rect.collidepoint(mx, my):
                r = max(1, self.toolbar.current_size // 2)
                pygame.draw.circle(surface, self.toolbar.color, (mx, my), r)

        # Fill cursor dot
        if self.toolbar.active and self.toolbar.tool == TOOL_FILL:
            mx, my = pygame.mouse.get_pos()
            if self._canvas_rect.collidepoint(mx, my):
                pygame.draw.circle(surface, (0, 0, 0), (mx, my), 4)

        if self.toolbar.active and self.toolbar.tool == TOOL_EYEDROPPER:
            self._draw_eyedropper_preview(surface)

    def _draw_eyedropper_preview(self, surface: pygame.Surface):
        mx, my = pygame.mouse.get_pos()
        if self._canvas_rect.collidepoint(mx, my):
            cx = mx - self._canvas_rect.x
            cy = my - self._canvas_rect.y
            color = self.canvas.get_color_at(cx, cy)
        else:
            color = self.toolbar.color
        cx_, cy_ = mx + 16, my - 16
        pygame.draw.circle(surface, color,      (cx_, cy_), 11)
        pygame.draw.circle(surface, (0, 0, 0),  (cx_, cy_), 11, 2)

    def _draw_round_end(self, surface: pygame.Surface):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        panel = pygame.Rect(W // 2 - 260, H // 2 - 130, 520, 260)
        draw_panel(surface, panel, bg=WHITE, radius=14)

        draw_text(surface, "The word was…", self.fonts["md"], TEXT_MID,
                  W // 2, panel.y + 28, anchor="center")
        draw_text(surface, self._round_end_overlay["word"].upper(),
                  self.fonts["xl"], ACCENT,
                  W // 2, panel.y + 68, anchor="center")

        scores = self._round_end_overlay["scores"]
        y      = panel.y + 120
        for entry in scores[:5]:
            draw_text(surface, entry["name"], self.fonts["sm"], TEXT_DARK,
                      W // 2 - 80, y, anchor="midleft")
            draw_text(surface, str(entry["score"]), self.fonts["sm"], ACCENT,
                      W // 2 + 80, y, anchor="midright")
            y += 24

    def _draw_word_choice(self, surface: pygame.Surface):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))

        panel = pygame.Rect(W // 2 - 280, H // 2 - 100, 560, 200)
        draw_panel(surface, panel, bg=WHITE, radius=14)

        draw_text(surface, "Choose a word to draw!", self.fonts["lg"], TEXT_DARK,
                  W // 2, panel.y + 26, anchor="center")

        btn_w = 150
        total = len(self._word_choices) * btn_w + (len(self._word_choices) - 1) * 16
        bx    = W // 2 - total // 2
        by    = panel.y + 90

        mx, my = pygame.mouse.get_pos()
        new_hov = None
        for word in self._word_choices:
            br   = pygame.Rect(bx, by, btn_w, 52)
            hovered = br.collidepoint(mx, my)
            col  = BTN_ORANGE_DARK if hovered else BTN_ORANGE
            pygame.draw.rect(surface, col, br, border_radius=8)
            draw_text(surface, word, self.fonts["btn_md"], WHITE,
                      br.centerx, br.centery, anchor="center")
            if hovered:
                new_hov = word
            bx += btn_w + 16
        if new_hov != self._hovered_word:
            self._hovered_word = new_hov
            if new_hov:
                sounds.play("hover")

    def _hit_word_choice(self, pos) -> str | None:
        btn_w = 150
        total = len(self._word_choices) * btn_w + (len(self._word_choices) - 1) * 16
        bx    = W // 2 - total // 2
        by    = H // 2 - 100 + 90

        for word in self._word_choices:
            if pygame.Rect(bx, by, btn_w, 52).collidepoint(pos):
                return word
            bx += btn_w + 16
        return None
