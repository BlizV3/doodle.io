import socket
import threading
import json
import time
import pygame
import os
from client.utils import (
    WHITE, ACCENT, TEXT_DARK, TEXT_MID, BORDER,
    BTN_ORANGE, BTN_ORANGE_DARK, AVATAR_COLORS,
    draw_text, draw_panel, draw_panel_alpha, get_background,
)
from client.components.input_box import InputBox
from client.pfp import get_pfp
import client.sounds as sounds

_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets")
)

def _load_icon(name: str, size: int) -> "pygame.Surface":
    path = os.path.join(_ASSETS_DIR, name)
    img  = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))

W, H = 1280, 720
BEACON_PORT = 5556
_SCAN_SECS  = 2.5


def _check_room_code(host: str, port: int, code: str) -> tuple[bool, str]:
    """Open a lightweight TCP probe connection to validate a room code."""
    try:
        with socket.create_connection((host, port), timeout=3.0) as sock:
            from shared.protocol import pack as _pack, unpack as _unpack
            from shared.protocol import CHECK_CODE as _CC, CODE_RESULT as _CR
            sock.sendall(_pack(_CC, room_code=code))
            sock.settimeout(3.0)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(1024)
                if not chunk:
                    return False, "Server closed connection."
                buf += chunk
            line = buf.split(b"\n")[0].strip()
            msg  = _unpack(line)
            if msg.get("type") == _CR:
                if msg.get("ok"):
                    return True, ""
                return False, msg.get("error", "Wrong room code.")
            return False, "Unexpected server response."
    except socket.timeout:
        return False, "Server did not respond."
    except OSError:
        return False, "Could not reach server."

_GRAY      = (140, 148, 160)
_GRAY_DARK = (100, 108, 118)

# Server list panel dimensions
_PANEL = pygame.Rect(W // 2 - 330, 148, 660, 350)
_ROW_H = 64
_ROW_S = 74    # stride between rows


# Listen on the UDP beacon port for ~2.5 s and collect unique server announcements.
def _scan_lan() -> list[dict]:
    seen: dict[tuple, dict] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.15)
    try:
        sock.bind(("", BEACON_PORT))
    except OSError:
        sock.close()
        return []

    deadline = time.time() + _SCAN_SECS
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
            msg = json.loads(data.decode().strip())
            if msg.get("type") == "server_beacon":
                host = msg.get("host") or addr[0]
                port = int(msg.get("port", 5555))
                key  = (host, port)
                seen[key] = {
                    "host":      host,
                    "port":      port,
                    "players":   int(msg.get("players", 0)),
                    "room_name": str(msg.get("room_name", "")),
                    "owner":     str(msg.get("owner", "")),
                    "owner_pfp": int(msg.get("owner_pfp", -1)),
                    "has_code":  bool(msg.get("has_code", False)),
                }
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    sock.close()
    return list(seen.values())


class JoinScreen:
    # Build all input boxes, server-list panel rects, code popup widgets, and start a LAN scan.
    def __init__(self, fonts: dict):
        self.fonts   = fonts
        self.error   = ""
        self._servers: list[dict] = []
        self._sel     = -1
        self._scanning = False

        cx = W // 2
        self._host_box = InputBox(
            pygame.Rect(cx - 200, 558, 230, 42),
            fonts["md"], placeholder="localhost", max_len=64,
        )
        self._port_box = InputBox(
            pygame.Rect(cx + 40, 558, 80, 42),
            fonts["md"], placeholder="5555", max_len=5,
        )
        self._code_box = InputBox(
            pygame.Rect(cx - 100, 608, 200, 42),
            fonts["md"], placeholder="Room code", max_len=16,
        )
        self._connect_btn = pygame.Rect(cx - 110, 660, 220, 48)
        self._back_btn    = pygame.Rect(24, 24, 42, 42)
        # Refresh button — top-right corner above the server list panel
        self._refresh_btn = pygame.Rect(_PANEL.right - 120, _PANEL.y - 38, 120, 32)

        self._hovered: str | None = None
        self._back_icon = _load_icon("back.png", 28)

        # Code-entry popup (shown when joining a code-protected room)
        _pp = pygame.Rect(cx - 200, H // 2 - 100, 400, 200)
        self._popup_panel  = _pp
        self._popup_input  = InputBox(
            pygame.Rect(_pp.x + 40, _pp.y + 60, _pp.width - 80, 44),
            fonts["md"], placeholder="Enter code…", max_len=16,
        )
        self._popup_ok     = pygame.Rect(_pp.x + 20,         _pp.y + 148, 140, 40)
        self._popup_cancel = pygame.Rect(_pp.right - 160,    _pp.y + 148, 140, 40)
        self._popup_active   = False
        self._popup_srv_idx  = -1
        self._popup_error    = ""

        self._start_scan()

    # ── scan ──────────────────────────────────────────────────────────────────

    # Kick off a background thread to refresh the LAN server list.
    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self._servers  = []
        self._sel      = -1
        threading.Thread(target=self._scan_worker, daemon=True).start()

    # Run the LAN scan in a background thread and store the results.
    def _scan_worker(self):
        self._servers  = _scan_lan()
        self._scanning = False

    # ── layout helpers ────────────────────────────────────────────────────────

    # Return the bounding rect for server list row i.
    def _row_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(_PANEL.x + 10, _PANEL.y + 10 + i * _ROW_S,
                           _PANEL.width - 20, _ROW_H)

    # Return the rect for the Join button inside server list row i.
    def _join_btn_rect(self, i: int) -> pygame.Rect:
        row = self._row_rect(i)
        return pygame.Rect(row.right - 74, row.centery - 18, 64, 36)

    def _code_visible(self) -> bool:
        return 0 <= self._sel < len(self._servers) and self._servers[self._sel].get("has_code")

    # ── events ────────────────────────────────────────────────────────────────

    # Route mouse and keyboard events to the popup, server list, or manual-connect inputs.
    def handle_event(self, event) -> dict | None:
        # Popup captures everything when active
        if self._popup_active:
            self._popup_input.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._popup_active = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return self._submit_popup()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._popup_ok.collidepoint(event.pos):
                    sounds.play("click")
                    return self._submit_popup()
                elif self._popup_cancel.collidepoint(event.pos):
                    sounds.play("click")
                    self._popup_active = False
            return None

        self._host_box.handle_event(event)
        self._port_box.handle_event(event)
        self._code_box.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._back_btn.collidepoint(event.pos):
                sounds.play("click")
                return {"action": "back"}
            if self._refresh_btn.collidepoint(event.pos):
                sounds.play("click")
                self._start_scan()
            if self._connect_btn.collidepoint(event.pos):
                sounds.play("click")
                return self._build_connect()

            for i, srv in enumerate(self._servers):
                if self._join_btn_rect(i).collidepoint(event.pos):
                    sounds.play("click")
                    if srv.get("has_code"):
                        self._open_popup(i)
                    else:
                        self._sel = i
                        return self._build_connect()
                    return None
                if self._row_rect(i).collidepoint(event.pos):
                    sounds.play("click")
                    self._sel = i

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._build_connect()

        return None

    # Show the room-code entry popup for the server at the given list index.
    def _open_popup(self, idx: int):
        self._popup_srv_idx     = idx
        self._popup_active      = True
        self._popup_error       = ""
        self._popup_input.text  = ""
        self._popup_input.active = True

    # Validate the popup code against the server and return a connect action on success.
    def _submit_popup(self) -> dict | None:
        code = self._popup_input.text.strip()
        if not code:
            self._popup_error = "Please enter a code."
            return None
        s = self._servers[self._popup_srv_idx]
        ok, err = _check_room_code(s["host"], s["port"], code)
        if not ok:
            self._popup_error = err
            return None
        self._popup_active = False
        return {"action": "connect", "host": s["host"], "port": s["port"], "room_code": code}

    # Build a connect action from the selected server row or the manual host/port inputs.
    def _build_connect(self) -> dict | None:
        if 0 <= self._sel < len(self._servers):
            s = self._servers[self._sel]
            if s.get("has_code"):
                self._open_popup(self._sel)
                return None
            return {"action": "connect", "host": s["host"], "port": s["port"], "room_code": ""}
        host = self._host_box.text.strip() or "localhost"
        try:
            port = int(self._port_box.text.strip() or "5555")
        except ValueError:
            self.error = "Invalid port number."
            return None
        self.error = ""
        code = self._code_box.text.strip()
        return {"action": "connect", "host": host, "port": port, "room_code": code}

    # Tick all input boxes so cursor blinking stays alive.
    def update(self, dt_ms: int):
        self._host_box.update(dt_ms)
        self._port_box.update(dt_ms)
        self._code_box.update(dt_ms)
        self._popup_input.update(dt_ms)

    # ── render ────────────────────────────────────────────────────────────────

    # Draw the server list panel, manual-connection inputs, and the optional code popup.
    def render(self, surface: pygame.Surface):
        surface.blit(get_background(), (0, 0))

        draw_text(surface, "Join a Game", self.fonts["xl"], WHITE,
                  W // 2, 42, anchor="center")

        draw_panel_alpha(surface, _PANEL,
                         bg_rgba=(10, 22, 60, 38),
                         border_rgba=(80, 140, 255, 80), radius=12)
        draw_text(surface, "Available Servers on your Network", self.fonts["sm"], (210, 235, 255),
                  _PANEL.x, _PANEL.y - 26, anchor="topleft")

        mx, my = pygame.mouse.get_pos()

        # Refresh button — above right side of panel
        rc = BTN_ORANGE_DARK if self._refresh_btn.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, rc, self._refresh_btn, border_radius=8)
        draw_text(surface, "Scanning…" if self._scanning else "Refresh",
                  self.fonts["btn_sm"], WHITE,
                  self._refresh_btn.centerx, self._refresh_btn.centery, anchor="center")

        if not self._servers:
            msg = "Scanning for servers…" if self._scanning else "No servers found on this network."
            draw_text(surface, msg, self.fonts["sm"], (160, 190, 230),
                      _PANEL.centerx, _PANEL.centery, anchor="center")
        else:
            for i, srv in enumerate(self._servers):
                row     = self._row_rect(i)
                is_sel  = i == self._sel
                hovered = row.collidepoint(mx, my) and not self._popup_active
                if is_sel:
                    pygame.draw.rect(surface, ACCENT, row, border_radius=8)
                elif hovered:
                    pygame.draw.rect(surface, (40, 70, 150), row, border_radius=8)

                fg = WHITE if (is_sel or hovered) else (200, 225, 255)

                # Owner pfp
                pfp_cx, pfp_cy = row.x + 26, row.centery
                pfp_r = 18
                pfp = get_pfp(srv.get("owner_pfp", -1), pfp_r)
                if pfp is not None:
                    pygame.draw.circle(surface, ACCENT, (pfp_cx, pfp_cy), pfp_r + 2)
                    surface.blit(pfp, pfp.get_rect(center=(pfp_cx, pfp_cy)))
                else:
                    av_col = AVATAR_COLORS[i % len(AVATAR_COLORS)]
                    pygame.draw.circle(surface, av_col, (pfp_cx, pfp_cy), pfp_r)
                    owner_initial = (srv.get("owner") or "?")[0].upper()
                    draw_text(surface, owner_initial, self.fonts["sm"], WHITE,
                              pfp_cx, pfp_cy, anchor="center")

                # Room name + owner
                text_x = row.x + 54
                room_name  = srv.get("room_name") or f"{srv['host']}:{srv['port']}"
                owner_name = srv.get("owner", "")
                draw_text(surface, room_name[:28], self.fonts["btn_md"], fg,
                          text_x, row.centery - 10, anchor="midleft")
                draw_text(surface, f"{owner_name}  ·  {srv['players']} player(s)",
                          self.fonts["sm"], fg,
                          text_x, row.centery + 12, anchor="midleft")

                # Lock label if code-protected
                if srv.get("has_code"):
                    draw_text(surface, "🔒 code", self.fonts["sm"], (255, 210, 80),
                              self._join_btn_rect(i).x - 60, row.centery, anchor="midleft")

                # Join button
                jb  = self._join_btn_rect(i)
                jc  = BTN_ORANGE_DARK if (jb.collidepoint(mx, my) and not self._popup_active) else BTN_ORANGE
                pygame.draw.rect(surface, jc, jb, border_radius=8)
                draw_text(surface, "Join", self.fonts["btn_sm"], WHITE,
                          jb.centerx, jb.centery, anchor="center")

        # Manual connection section
        draw_text(surface, "Or connect manually:", self.fonts["sm"], (210, 235, 255),
                  W // 2 - 200, 538, anchor="midleft")
        self._host_box.draw(surface)
        self._port_box.draw(surface)

        code_vis = self._code_visible()
        lbl_col  = (210, 235, 255) if code_vis else (140, 148, 165)
        draw_text(surface, "Room Code:", self.fonts["sm"], lbl_col,
                  W // 2 - 200, 629, anchor="midleft")
        self._code_box.draw(surface, enabled=code_vis)

        col = BTN_ORANGE_DARK if self._connect_btn.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, col, self._connect_btn, border_radius=10)
        draw_text(surface, "Connect", self.fonts["lg"], WHITE,
                  self._connect_btn.centerx, self._connect_btn.centery, anchor="center")

        # Back icon button
        back_rgba = (18, 36, 90, 60) if self._back_btn.collidepoint(mx, my) else (10, 22, 60, 38)
        draw_panel_alpha(surface, self._back_btn, bg_rgba=back_rgba,
                         border_rgba=(80, 140, 255, 80), radius=10)
        surface.blit(self._back_icon,
                     self._back_icon.get_rect(center=self._back_btn.center))

        if self.error:
            draw_text(surface, self.error, self.fonts["sm"], (220, 60, 60),
                      W // 2, H - 18, anchor="center")

        # Popup drawn last (on top of everything)
        if self._popup_active:
            self._draw_code_popup(surface)

        # Hover sounds (skip when popup is open)
        if not self._popup_active:
            new_hov = None
            if self._back_btn.collidepoint(mx, my):         new_hov = "back"
            elif self._refresh_btn.collidepoint(mx, my):    new_hov = "refresh"
            elif self._connect_btn.collidepoint(mx, my):    new_hov = "connect"
            else:
                for i in range(len(self._servers)):
                    if self._join_btn_rect(i).collidepoint(mx, my):
                        new_hov = f"join_{i}"; break
                    if self._row_rect(i).collidepoint(mx, my):
                        new_hov = f"row_{i}"; break
            if new_hov != self._hovered:
                self._hovered = new_hov
                if new_hov:
                    sounds.play("hover")

    # ── popup ─────────────────────────────────────────────────────────────────

    # Draw the modal code-entry popup with a translucent veil over the screen.
    def _draw_code_popup(self, surface: pygame.Surface):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 165))
        surface.blit(veil, (0, 0))

        draw_panel(surface, self._popup_panel, bg=WHITE, radius=16)

        draw_text(surface, "Enter Room Code", self.fonts["lg"], TEXT_DARK,
                  self._popup_panel.centerx, self._popup_panel.y + 28, anchor="center")

        self._popup_input.draw(surface)

        if self._popup_error:
            draw_text(surface, self._popup_error, self.fonts["sm"], (210, 60, 60),
                      self._popup_panel.centerx, self._popup_panel.y + 116, anchor="center")

        mx, my = pygame.mouse.get_pos()

        ok_col = BTN_ORANGE_DARK if self._popup_ok.collidepoint(mx, my) else BTN_ORANGE
        pygame.draw.rect(surface, ok_col, self._popup_ok, border_radius=8)
        draw_text(surface, "Join", self.fonts["btn_md"], WHITE,
                  self._popup_ok.centerx, self._popup_ok.centery, anchor="center")

        cc = _GRAY_DARK if self._popup_cancel.collidepoint(mx, my) else _GRAY
        pygame.draw.rect(surface, cc, self._popup_cancel, border_radius=8)
        draw_text(surface, "Cancel", self.fonts["btn_md"], WHITE,
                  self._popup_cancel.centerx, self._popup_cancel.centery, anchor="center")
