# -*- coding: utf-8 -*-
import threading
from server.room import Room
from server.player import Player
from server.word_manager import WordManager


class GameManager:
    # Initialize with a shared WordManager, an empty room map, a thread lock, and an ID counter.
    def __init__(self):
        self._word_mgr = WordManager()
        self._rooms: dict[str, Room] = {}
        self._lock = threading.Lock()
        self._next_id = 1

    # Return lobby metadata from the first active room for the LAN beacon, or None if no rooms.
    def get_beacon_info(self) -> dict | None:
        with self._lock:
            for room in self._rooms.values():
                return {
                    "room_name":  room.room_name,
                    "owner":      room._owner_name,
                    "owner_pfp":  room._owner_pfp_idx,
                    "players":    room.player_count(),
                    "has_code":   bool(room.room_code),
                }
        return None

    def assign_room(self, player: Player, settings: dict | None = None,
                    room_code: str = "") -> tuple:
        """Put player in an open room (or create one with settings).
        Returns (room, error_str). error_str is '' on success."""
        with self._lock:
            for room in self._rooms.values():
                if room.state == "waiting" and room.player_count() < room.max_players:
                    if room.room_code and room_code.strip().upper() != room.room_code.strip().upper():
                        return None, "Wrong room code."
                    break
            else:
                room_id = f"room_{self._next_id}"
                self._next_id += 1
                room = Room(room_id, self._word_mgr, settings)
                self._rooms[room_id] = room

        added = room.add_player(player)
        if not added:
            return None, "Room is full."
        return room, ""

    def check_room_code(self, code: str) -> tuple[bool, str]:
        """Lightweight code probe — does NOT add the player to any room."""
        with self._lock:
            for room in self._rooms.values():
                if room.state == "waiting" and room.player_count() < room.max_players:
                    if room.room_code:
                        if code.strip().upper() != room.room_code.strip().upper():
                            return False, "Wrong room code."
                    return True, ""
        return False, "No room available."

    # Remove a player from their room and clean up the room entry if it becomes empty.
    def remove_player(self, player: Player, room: Room):
        room.remove_player(player)
        with self._lock:
            if room.player_count() == 0:
                self._rooms.pop(room.room_id, None)
