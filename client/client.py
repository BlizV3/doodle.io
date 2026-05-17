# -*- coding: utf-8 -*-
"""
Run with:  python client/client.py
"""
import sys
import os
import socket
import subprocess
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
from shared.protocol import (
    JOIN, PLAYER_LIST, GAME_START, ROUND_START, CHOOSE_WORD, WORD_CHOSEN,
    HINT_UPDATE, TIMER_UPDATE, CHAT_MSG, ROUND_END, GAME_END, DISCONNECT,
    DRAW, DRAW_FILL, DRAW_CLEAR, DRAW_SNAPSHOT, WORD_CHOICE, GUESS,
    KICK_PLAYER, CLOSE_ROOM, KICKED, ROOM_CLOSED, START_GAME_REQ, ERROR,
)
from client.network  import NetworkClient
from client.utils    import make_fonts
import client.sounds as sounds

from client.screens.profile_screen          import ProfileScreen
from client.screens.profile_designer_screen import ProfileDesignerScreen
from client.screens.main_menu_screen   import MainMenuScreen
from client.screens.create_room_screen import CreateRoomScreen
from client.screens.join_screen        import JoinScreen
from client.screens.waiting_screen     import WaitingScreen
from client.screens.game_screen        import GameScreen
from client.screens.end_screen         import EndScreen

W, H  = 1280, 720
FPS   = 60
TITLE = "doodle.io"
_SERVER_PORT = 5555


# Spawn the server subprocess and wait up to 5 seconds for the TCP port to become available.
def _launch_server() -> subprocess.Popen | None:
    root = os.path.join(os.path.dirname(__file__), "..")
    proc = subprocess.Popen(
        [sys.executable, os.path.join("server", "server.py")],
        cwd=os.path.abspath(root),
    )
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", _SERVER_PORT), timeout=0.3):
                pass
            time.sleep(0.05)
            return proc
        except OSError:
            time.sleep(0.1)
    return proc


# Initialize pygame, run the screen state machine, and pump the network message queue each frame.
def main():
    pygame.init()
    sounds.init()
    pygame.display.set_caption(TITLE)
    _icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    try:
        pygame.display.set_icon(pygame.image.load(_icon_path))
    except Exception:
        pass
    screen = pygame.display.set_mode((W, H))
    clock  = pygame.time.Clock()
    fonts  = make_fonts()

    net         = NetworkClient()
    local_name  = ""
    pfp_idx     = 0
    pfp_surf    = None
    server_proc = None
    current     = ProfileScreen(fonts)

    _prev_player_count = -1
    _prev_player_names: set[str] = set()
    _guessed_count     = 0
    _total_guessers    = 0

    running = True
    while running:
        dt = clock.tick(FPS)

        events = pygame.event.get()
        for ev in events:
            if ev.type == pygame.QUIT:
                running = False
                break

        if not running:
            break

        action = None

        # ── ProfileScreen ─────────────────────────────────────────────────────
        if isinstance(current, ProfileScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result:
                    action = result
            current.update(dt)
            if action:
                if action["action"] == "profile_done":
                    local_name = action["name"]
                    pfp_idx    = action["pfp_idx"]
                    pfp_surf   = action["pfp_surf"]
                    current    = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)
                elif action["action"] == "design_pfp":
                    current = ProfileDesignerScreen(fonts, action.get("name", ""))

        # ── ProfileDesignerScreen ─────────────────────────────────────────────
        elif isinstance(current, ProfileDesignerScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result:
                    action = result
            current.update(dt)
            if action:
                prev_name = action.get("prev_name", local_name)
                if action["action"] == "pfp_saved":
                    pfp_idx = action["pfp_idx"]
                current = ProfileScreen(fonts, prev_name, pfp_idx)

        # ── MainMenuScreen ────────────────────────────────────────────────────
        elif isinstance(current, MainMenuScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result:
                    action = result
            current.update(dt)
            if action:
                if action["action"] == "create":
                    current = CreateRoomScreen(fonts)
                elif action["action"] == "join":
                    current = JoinScreen(fonts)

        # ── CreateRoomScreen ──────────────────────────────────────────────────
        elif isinstance(current, CreateRoomScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result:
                    action = result
            current.update(dt)
            if action:
                if action["action"] == "back":
                    current = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)
                elif action["action"] == "create":
                    settings = action["settings"]
                    server_proc = _launch_server()
                    try:
                        net.connect("localhost", _SERVER_PORT)
                        net.send(JOIN, name=local_name, pfp_idx=pfp_idx,
                                 settings=settings)
                        current = WaitingScreen(fonts, local_name)
                    except OSError as e:
                        current.error = f"Could not start server: {e}"

        # ── JoinScreen ────────────────────────────────────────────────────────
        elif isinstance(current, JoinScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result:
                    action = result
            current.update(dt)
            if action:
                if action["action"] == "connect":
                    try:
                        net.connect(action["host"], action["port"])
                        net.send(JOIN, name=local_name, pfp_idx=pfp_idx,
                                 room_code=action.get("room_code", ""))
                        current = WaitingScreen(fonts, local_name)
                    except OSError as e:
                        current.error = f"Could not connect: {e}"
                elif action["action"] == "back":
                    current = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)

        # ── WaitingScreen ─────────────────────────────────────────────────────
        elif isinstance(current, WaitingScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result:
                    act = result["action"]
                    if act == "leave":
                        net.disconnect()
                        net = NetworkClient()
                        if server_proc:
                            server_proc.terminate()
                            server_proc = None
                        current = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)
                    elif act == "kick":
                        net.send(KICK_PLAYER, name=result["name"])
                    elif act == "close_room":
                        net.send(CLOSE_ROOM)
                    elif act == "start_game":
                        net.send(START_GAME_REQ)
            current.update(dt)

        # ── GameScreen ────────────────────────────────────────────────────────
        elif isinstance(current, GameScreen):
            outgoing: list[dict] = []
            for ev in events:
                outgoing.extend(current.handle_event(ev))
            current.tick(dt)
            for msg in outgoing:
                _send_game_msg(net, msg)

        # ── EndScreen ─────────────────────────────────────────────────────────
        elif isinstance(current, EndScreen):
            for ev in events:
                result = current.handle_event(ev)
                if result and result.get("action") == "play_again":
                    net.disconnect()
                    net = NetworkClient()
                    if server_proc:
                        server_proc.terminate()
                        server_proc = None
                    current = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)

        # ── Network poll ──────────────────────────────────────────────────────
        if not isinstance(current, (ProfileScreen, ProfileDesignerScreen, MainMenuScreen, CreateRoomScreen, JoinScreen)):
            for msg in net.poll():
                t = msg.get("type")

                if t == ERROR:
                    err_text = msg.get("text", "Connection failed.")
                    net.disconnect()
                    net = NetworkClient()
                    if server_proc:
                        server_proc.terminate()
                        server_proc = None
                    join       = JoinScreen(fonts)
                    join.error = err_text
                    current    = join
                    break

                elif t == DISCONNECT:
                    net.disconnect()
                    net = NetworkClient()
                    if server_proc:
                        server_proc.terminate()
                        server_proc = None
                    menu       = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)
                    menu.error = "Disconnected from server."
                    current    = menu
                    break

                elif t == KICKED:
                    net.disconnect()
                    net = NetworkClient()
                    if server_proc:
                        server_proc.terminate()
                        server_proc = None
                    menu       = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)
                    menu.error = "You were kicked from the room."
                    current    = menu
                    break

                elif t == ROOM_CLOSED:
                    net.disconnect()
                    net = NetworkClient()
                    if server_proc:
                        server_proc.terminate()
                        server_proc = None
                    menu       = MainMenuScreen(fonts, local_name, pfp_idx, pfp_surf)
                    menu.error = "The room was closed."
                    current    = menu
                    break

                elif t == PLAYER_LIST:
                    players    = msg["players"]
                    new_count  = len(players)
                    new_names  = {p["name"] for p in players}
                    if _prev_player_count >= 0:
                        if new_count > _prev_player_count:
                            sounds.play("Join")
                        elif new_count < _prev_player_count:
                            sounds.play("Leave")
                            if isinstance(current, GameScreen):
                                from client.components.chat_box import COLOR_LEAVE
                                for name in (_prev_player_names - new_names):
                                    current.chat.add_system(f"{name} left the game.", color=COLOR_LEAVE)
                    _prev_player_count = new_count
                    _prev_player_names = new_names
                    new_guessed = sum(1 for p in players if p.get("has_guessed"))
                    if new_guessed > _guessed_count and isinstance(current, GameScreen):
                        sounds.play("Playerguessed")
                    _guessed_count  = new_guessed
                    _total_guessers = sum(1 for p in players if not p.get("is_drawing", False))
                    if isinstance(current, WaitingScreen):
                        current.update_players(players, msg.get("owner", ""),
                                               msg.get("max_players", 6),
                                               msg.get("room_code", ""),
                                               msg.get("room_name", ""))
                    elif isinstance(current, GameScreen):
                        current.update(msg)

                elif t == GAME_START:
                    _prev_player_count = -1
                    current = GameScreen(fonts, local_name)

                elif t == ROUND_START:
                    _guessed_count  = 0
                    _total_guessers = 0
                    sounds.play("Roundstart")
                    if isinstance(current, GameScreen):
                        current.update(msg)

                elif t == TIMER_UPDATE:
                    if msg.get("remaining", 999) <= 10:
                        sounds.play("Tick")
                    if isinstance(current, GameScreen):
                        current.update(msg)

                elif t == ROUND_END:
                    if _total_guessers > 0 and _guessed_count / _total_guessers > 0.5:
                        sounds.play("Roundendsuccess")
                    else:
                        sounds.play("Roundendfailure")
                    if isinstance(current, GameScreen):
                        current.update(msg)

                elif t in (CHOOSE_WORD, WORD_CHOSEN, HINT_UPDATE,
                           DRAW, DRAW_FILL, DRAW_CLEAR, DRAW_SNAPSHOT, CHAT_MSG):
                    if isinstance(current, GameScreen):
                        current.update(msg)

                elif t == GAME_END:
                    if isinstance(current, GameScreen):
                        current = EndScreen(fonts, msg["scores"])

        # ── Render ────────────────────────────────────────────────────────────
        current.render(screen)
        pygame.display.flip()

    net.disconnect()
    if server_proc:
        server_proc.terminate()
    pygame.quit()
    sys.exit(0)


# Route an outgoing game message dict to the correct net.send() call.
def _send_game_msg(net: NetworkClient, msg: dict):
    t = msg.get("type")
    if t == DRAW:
        net.send(DRAW, x1=msg["x1"], y1=msg["y1"],
                 x2=msg["x2"], y2=msg["y2"],
                 color=msg["color"], size=msg["size"])
    elif t == DRAW_FILL:
        net.send(DRAW_FILL, x=msg["x"], y=msg["y"], color=msg["color"])
    elif t == DRAW_CLEAR:
        net.send(DRAW_CLEAR)
    elif t == DRAW_SNAPSHOT:
        net.send(DRAW_SNAPSHOT, data=msg["data"])
    elif t == WORD_CHOICE:
        net.send(WORD_CHOICE, word=msg["word"])
    elif t == GUESS:
        net.send(GUESS, text=msg["text"])


if __name__ == "__main__":
    main()
