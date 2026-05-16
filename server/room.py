# -*- coding: utf-8 -*-
import time
import threading
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.protocol import (
    pack, PLAYER_LIST, GAME_START, ROUND_START, CHOOSE_WORD, WORD_CHOSEN,
    HINT_UPDATE, TIMER_UPDATE, CHAT_MSG, ROUND_END, GAME_END, DRAW_FILL,
    DRAW_SNAPSHOT, KICKED, ROOM_CLOSED,
)
from server.player import Player
from server.word_manager import WordManager

CHOOSE_TIME  = 15
END_TIME     = 6


class RoomState:
    WAITING   = "waiting"
    CHOOSING  = "choosing"
    DRAWING   = "drawing"
    ROUND_END = "round_end"
    GAME_END  = "game_end"


class Room:
    def __init__(self, room_id: str, word_mgr: WordManager, settings: dict | None = None):
        s = settings or {}
        self.room_id      = room_id
        self.word_mgr     = word_mgr

        # Configurable game settings
        self.max_players  = max(2, min(10, int(s.get("max_players", 6))))
        self.draw_time    = max(15, min(300, int(s.get("draw_time", 80))))
        self.total_rounds = max(1, min(10, int(s.get("rounds", 3))))
        self.word_count   = max(1, min(5,  int(s.get("word_count", 3))))
        self.hint_count   = max(0, min(5,  int(s.get("hints", 2))))
        self.custom_words = bool(s.get("custom_words", False))
        self.word_list    = [str(w) for w in s.get("word_list", []) if str(w).strip()]
        self.room_name    = str(s.get("room_name", "My Room"))[:30].strip() or "My Room"
        self.room_code    = str(s.get("room_code", ""))[:16].strip()

        self.players: list[Player] = []
        self.state     = RoomState.WAITING
        self.lock      = threading.Lock()

        self._owner_name    = ""
        self._owner_pfp_idx = 0
        self._drawer_idx   = -1
        self._current_word = ""
        self._word_choices: list[str] = []
        self._revealed: set[int] = set()
        self._guessed_count  = 0
        self._current_round  = 0
        self._timer_ver      = 0
        self._draw_start_time: float = 0.0
        self._gained: dict[str, int] = {}   # points earned this round

    # ── Player management ────────────────────────────────────────────────────

    def add_player(self, player: Player) -> bool:
        """Add player; returns False if room is full."""
        with self.lock:
            if len(self.players) >= self.max_players:
                return False
            if not self.players:
                self._owner_name    = player.name
                self._owner_pfp_idx = player.pfp_idx
            self.players.append(player)
        self._broadcast_player_list()
        return True

    def remove_player(self, player: Player):
        with self.lock:
            if player not in self.players:
                return
            was_drawing = player.is_drawing
            self.players.remove(player)

        self._broadcast_player_list()

        if self.state == RoomState.DRAWING and was_drawing:
            self._end_round(forced=True)
        elif self.state not in (RoomState.WAITING, RoomState.GAME_END):
            if len(self.players) < 2:
                self._end_game()

    def player_count(self) -> int:
        return len(self.players)

    # ── Game flow ────────────────────────────────────────────────────────────

    def handle_start_game(self, player: Player):
        """Owner-triggered game start."""
        if player.name != self._owner_name:
            return
        self.start_game()

    def start_game(self):
        with self.lock:
            if self.state != RoomState.WAITING or len(self.players) < 2:
                return
            for p in self.players:
                p.score = 0
            self._current_round = 0
            self._drawer_idx    = -1

        names = [p.name for p in self.players]
        print(f"[game] New game began with: {', '.join(names)}", flush=True)
        self._broadcast(pack(GAME_START, total_rounds=self.total_rounds))
        self._next_turn()

    def _next_turn(self):
        with self.lock:
            if not self.players:
                return
            self._drawer_idx = (self._drawer_idx + 1) % len(self.players)
            if self._drawer_idx == 0:
                self._current_round += 1

        if self._current_round > self.total_rounds:
            self._end_game()
            return

        with self.lock:
            for p in self.players:
                p.reset_round()
            self._guessed_count = 0
            self._revealed      = set()
            self._gained        = {}

            drawer = self.players[self._drawer_idx]
            drawer.is_drawing = True
            self._word_choices = self._pick_words()
            self.state = RoomState.CHOOSING

        self._broadcast_player_list()
        drawer = self.players[self._drawer_idx]
        print(f"[game] {drawer.name} is now choosing a word", flush=True)
        self._send(drawer, pack(CHOOSE_WORD, words=self._word_choices))
        self._start_timer(CHOOSE_TIME, self._on_choose_timeout)

    def _pick_words(self) -> list[str]:
        if self.custom_words and self.word_list:
            pool = self.word_list
            return random.sample(pool, min(self.word_count, len(pool)))
        return self.word_mgr.pick_words(self.word_count)

    def handle_word_choice(self, player: Player, word: str):
        with self.lock:
            if self.state != RoomState.CHOOSING:
                return
            if not player.is_drawing:
                return
            if word not in self._word_choices:
                return
            self._current_word = word
            self.state = RoomState.DRAWING
        self._begin_drawing_phase()

    def _on_choose_timeout(self):
        with self.lock:
            if self.state != RoomState.CHOOSING:
                return
            self._current_word = random.choice(self._word_choices)
            self.state = RoomState.DRAWING
        self._begin_drawing_phase()

    def _begin_drawing_phase(self):
        word   = self._current_word
        drawer = self.players[self._drawer_idx]
        hint   = WordManager.make_hint(word, set())
        print(f"[game] Word selected by {drawer.name}: '{word}'", flush=True)

        self._draw_start_time = time.time()
        self._broadcast(pack(WORD_CHOSEN, drawer=drawer.name))
        self._send(drawer, pack(
            ROUND_START, drawer=drawer.name, hint=list(word),
            round=self._current_round, total_rounds=self.total_rounds, time=self.draw_time,
        ))
        self._broadcast(
            pack(ROUND_START, drawer=drawer.name, hint=hint,
                 round=self._current_round, total_rounds=self.total_rounds, time=self.draw_time),
            exclude=drawer,
        )
        self._start_draw_timer()

    def _start_draw_timer(self):
        self._timer_ver += 1
        version    = self._timer_ver
        draw_time  = self.draw_time
        hint_count = self.hint_count

        # Formula: interval = draw_time / hint_count
        # Reveal k-th hint when remaining == draw_time - interval*k
        if hint_count > 0:
            interval = draw_time / hint_count
            reveal_at = sorted(
                [int(draw_time - interval * k) for k in range(1, hint_count + 1)],
                reverse=True,
            )
        else:
            reveal_at = []

        def loop():
            end_time       = time.time() + draw_time
            revealed_count = 0

            while version == self._timer_ver:
                remaining = int(end_time - time.time())
                if remaining <= 0:
                    if version == self._timer_ver:
                        self._on_draw_timeout()
                    break

                while revealed_count < len(reveal_at) and remaining <= reveal_at[revealed_count]:
                    self._reveal_hint()
                    revealed_count += 1

                self._broadcast(pack(TIMER_UPDATE, remaining=remaining))
                time.sleep(1.0)

        threading.Thread(target=loop, daemon=True).start()

    def _start_timer(self, duration: float, callback):
        self._timer_ver += 1
        version = self._timer_ver

        def run():
            end = time.time() + duration
            while version == self._timer_ver:
                remaining = int(end - time.time())
                if remaining < 0:
                    if version == self._timer_ver:
                        callback()
                    break
                self._broadcast(pack(TIMER_UPDATE, remaining=remaining))
                time.sleep(1.0)

        threading.Thread(target=run, daemon=True).start()

    def _reveal_hint(self):
        with self.lock:
            self._revealed = WordManager.reveal_random_letter(self._current_word, self._revealed)
            hint = WordManager.make_hint(self._current_word, self._revealed)
        self._broadcast(pack(HINT_UPDATE, hint=hint))

    def handle_guess(self, player: Player, text: str):
        route      = None
        send_text  = text
        all_guessed = False

        with self.lock:
            if player.is_drawing:
                return
            if self.state == RoomState.CHOOSING:
                route = "wrong"
            elif self.state == RoomState.DRAWING:
                if player.has_guessed:
                    route = "guessed"
                elif text.strip().lower() == self._current_word.lower():
                    player.has_guessed   = True
                    self._guessed_count += 1
                    elapsed    = time.time() - self._draw_start_time
                    time_ratio = max(0.0, 1.0 - elapsed / max(1, self.draw_time))
                    pos_bonus  = max(0, 200 - (self._guessed_count - 1) * 50)
                    pts        = max(50, int(time_ratio * 800) + pos_bonus)
                    player.score += pts
                    self._gained[player.name] = pts
                    all_guessed = self._guessed_count >= len(self.players) - 1
                    route = "correct"
                else:
                    route = "wrong"
            else:
                return

        if route == "guessed":
            print(f"[chat] -- {player.name}: {send_text}", flush=True)
            self._send_to_guessed_team(
                pack(CHAT_MSG, sender=player.name, text=send_text, guessed=True)
            )
        elif route == "wrong":
            print(f"[chat] {player.name}: {send_text}", flush=True)
            self._broadcast(pack(CHAT_MSG, sender=player.name, text=send_text, guessed=False))
        elif route == "correct":
            print(f"[game] {player.name} has guessed the word!", flush=True)
            self._broadcast(pack(
                CHAT_MSG, sender=player.name,
                text=f"{player.name} guessed the word!", guessed=True,
            ))
            self._broadcast_player_list()
            if all_guessed:
                self._end_round()

    def handle_draw(self, player: Player, data: dict):
        if not player.is_drawing or self.state != RoomState.DRAWING:
            return
        self._broadcast(pack(data["type"], **{k: v for k, v in data.items() if k != "type"}),
                        exclude=player)

    def handle_draw_fill(self, player: Player, x: int, y: int, color: list):
        if not player.is_drawing or self.state != RoomState.DRAWING:
            return
        self._broadcast(pack(DRAW_FILL, x=x, y=y, color=color), exclude=player)

    def handle_draw_clear(self, player: Player):
        if not player.is_drawing or self.state != RoomState.DRAWING:
            return
        from shared.protocol import DRAW_CLEAR
        self._broadcast(pack(DRAW_CLEAR), exclude=player)

    def handle_draw_snapshot(self, player: Player, data: str):
        if not player.is_drawing or self.state != RoomState.DRAWING:
            return
        self._broadcast(pack(DRAW_SNAPSHOT, data=data), exclude=player)

    def _on_draw_timeout(self):
        if self.state == RoomState.DRAWING:
            self._end_round()

    def _end_round(self, forced: bool = False):
        with self.lock:
            if self.state not in (RoomState.DRAWING, RoomState.CHOOSING):
                return
            self.state = RoomState.ROUND_END
            word       = self._current_word

            # Award drawer based on fraction of guessers who got the word
            total_guessers = max(1, len(self.players) - 1)
            drawer_pts = int(self._guessed_count / total_guessers * 500)
            if self._drawer_idx < len(self.players):
                drawer = self.players[self._drawer_idx]
                drawer.score += drawer_pts
                self._gained[drawer.name] = drawer_pts

            scores_snap = [
                {"name": p.name, "score": p.score, "gained": self._gained.get(p.name, 0)}
                for p in self.players
            ]
        print(f"[game] Round ended (word was '{word}')", flush=True)
        self._broadcast(pack(ROUND_END, word=word, scores=scores_snap))
        self._start_timer(END_TIME, self._next_turn)

    def _end_game(self):
        with self.lock:
            self.state  = RoomState.GAME_END
            scores_snap = sorted(
                [{"name": p.name, "score": p.score} for p in self.players],
                key=lambda x: x["score"], reverse=True,
            )
        self._broadcast(pack(GAME_END, scores=scores_snap))
        self._start_timer(10, self._reset)

    def _reset(self):
        with self.lock:
            for p in self.players:
                p.reset_round()
                p.score = 0
            self._drawer_idx    = -1
            self._current_round = 0
            self.state          = RoomState.WAITING
        self._broadcast_player_list()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _broadcast(self, data: bytes, exclude: Player = None):
        dead = []
        with self.lock:
            targets = list(self.players)
        for p in targets:
            if p is exclude:
                continue
            try:
                p.conn.sendall(data)
            except OSError:
                dead.append(p)
        for p in dead:
            self.remove_player(p)

    def _send(self, player: Player, data: bytes):
        try:
            player.conn.sendall(data)
        except OSError:
            self.remove_player(player)

    def _send_to_guessed_team(self, data: bytes):
        with self.lock:
            targets = [p for p in self.players if p.is_drawing or p.has_guessed]
        dead = []
        for p in targets:
            try:
                p.conn.sendall(data)
            except OSError:
                dead.append(p)
        for p in dead:
            self.remove_player(p)

    def handle_kick_player(self, requester: Player, target_name: str):
        if requester.name != self._owner_name:
            return
        with self.lock:
            target = next((p for p in self.players if p.name == target_name), None)
        if target is None or target.name == self._owner_name:
            return
        try:
            target.conn.sendall(pack(KICKED))
        except OSError:
            pass
        try:
            target.conn.close()
        except OSError:
            pass

    def handle_close_room(self, requester: Player):
        if requester.name != self._owner_name:
            return
        with self.lock:
            targets    = list(self.players)
            self.state = RoomState.GAME_END
        for p in targets:
            try:
                p.conn.sendall(pack(ROOM_CLOSED))
            except OSError:
                pass
        import time as _time
        _time.sleep(0.08)
        for p in targets:
            try:
                p.conn.close()
            except OSError:
                pass

    def _broadcast_player_list(self):
        with self.lock:
            player_dicts = [p.to_dict() for p in self.players]
            owner        = self._owner_name
        self._broadcast(pack(PLAYER_LIST, players=player_dicts, owner=owner,
                             max_players=self.max_players,
                             room_name=self.room_name,
                             room_code=self.room_code))
