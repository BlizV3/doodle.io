# -*- coding: utf-8 -*-
"""
Run with:  python server/server.py
           python server/server.py --host 0.0.0.0 --port 5555
"""
import sys
import os
import socket
import threading
import argparse
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.protocol import (
    pack, unpack,
    JOIN, GUESS, DRAW, DRAW_FILL, DRAW_CLEAR, DRAW_SNAPSHOT, WORD_CHOICE,
    JOINED, ERROR, KICK_PLAYER, CLOSE_ROOM, START_GAME_REQ,
    CHECK_CODE, CODE_RESULT,
)
from server.player import Player
from server.game_manager import GameManager

HOST        = "0.0.0.0"
PORT        = 5555
BEACON_PORT = 5556

_client_lock     = threading.Lock()
_client_count    = 0
_ever_had_client = False
_shutdown        = threading.Event()


def _on_client_connect():
    global _client_count, _ever_had_client
    with _client_lock:
        _client_count    += 1
        _ever_had_client  = True


def _on_client_disconnect():
    global _client_count
    with _client_lock:
        _client_count -= 1
        if _client_count == 0 and _ever_had_client:
            _shutdown.set()


def handle_client(conn: socket.socket, addr, game_mgr: GameManager):
    player  = Player(conn, addr)
    room    = None
    buf     = b""
    _joined = False

    print(f"[+] Connection from {addr}")

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data

            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = unpack(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                msg_type = msg.get("type")

                if room is None:
                    if msg_type == CHECK_CODE:
                        code     = str(msg.get("room_code", ""))
                        ok, err  = game_mgr.check_room_code(code)
                        conn.sendall(pack(CODE_RESULT, ok=ok, error=err))
                        break   # close this probe connection

                    if msg_type == JOIN:
                        if not _joined:
                            _on_client_connect()
                            _joined = True
                        name = str(msg.get("name", "")).strip()[:20] or "Player"
                        player.name    = name
                        player.pfp_idx = int(msg.get("pfp_idx", 0))
                        conn.sendall(pack(JOINED, name=name))
                        settings  = msg.get("settings") or {}
                        room_code = str(msg.get("room_code", ""))
                        room, err = game_mgr.assign_room(player, settings, room_code)
                        if room is None:
                            conn.sendall(pack(ERROR, text=err))
                            break
                    continue

                if msg_type == GUESS:
                    room.handle_guess(player, str(msg.get("text", "")))
                elif msg_type == DRAW:
                    room.handle_draw(player, msg)
                elif msg_type == DRAW_FILL:
                    room.handle_draw_fill(player, msg.get("x", 0), msg.get("y", 0), msg.get("color", [0,0,0]))
                elif msg_type == DRAW_CLEAR:
                    room.handle_draw_clear(player)
                elif msg_type == DRAW_SNAPSHOT:
                    room.handle_draw_snapshot(player, str(msg.get("data", "")))
                elif msg_type == WORD_CHOICE:
                    room.handle_word_choice(player, str(msg.get("word", "")))
                elif msg_type == KICK_PLAYER:
                    room.handle_kick_player(player, str(msg.get("name", "")))
                elif msg_type == CLOSE_ROOM:
                    room.handle_close_room(player)
                elif msg_type == START_GAME_REQ:
                    room.handle_start_game(player)

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        print(f"[-] Disconnected {player.name!r} {addr}")
        if room:
            game_mgr.remove_player(player, room)
        try:
            conn.close()
        except OSError:
            pass
        if _joined:
            _on_client_disconnect()


def _beacon_worker(port: int, game_mgr):
    import time
    try:
        lan_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        lan_ip = "127.0.0.1"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while not _shutdown.is_set():
        info = game_mgr.get_beacon_info()
        if info:
            payload = {
                "type":       "server_beacon",
                "host":       lan_ip,
                "port":       port,
                "players":    info["players"],
                "room_name":  info["room_name"],
                "owner":      info["owner"],
                "owner_pfp":  info["owner_pfp"],
                "has_code":   info["has_code"],
            }
        else:
            with _client_lock:
                count = _client_count
            payload = {
                "type":    "server_beacon",
                "host":    lan_ip,
                "port":    port,
                "players": count,
            }
        beacon = json.dumps(payload).encode() + b"\n"
        for dest in ("255.255.255.255", "127.0.0.1"):
            try:
                sock.sendto(beacon, (dest, BEACON_PORT))
            except OSError:
                pass
        _shutdown.wait(2.0)

    sock.close()


def main():
    parser = argparse.ArgumentParser(description="doodle.io server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    game_mgr = GameManager()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen(32)
        srv.settimeout(1.0)
        print(f"doodle.io server listening on {args.host}:{args.port}")
        threading.Thread(target=_beacon_worker, args=(args.port, game_mgr), daemon=True).start()

        while not _shutdown.is_set():
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            threading.Thread(
                target=handle_client, args=(conn, addr, game_mgr), daemon=True
            ).start()

    print("All clients disconnected — server shutting down.")


if __name__ == "__main__":
    main()
