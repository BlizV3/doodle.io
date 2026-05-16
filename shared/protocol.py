# -*- coding: utf-8 -*-
import json

# ── Client → Server ───────────────────────────────────────────────────────────
JOIN          = "join"           # {name, pfp_idx, settings?}
GUESS         = "guess"          # {text}
DRAW          = "draw"           # {x1,y1,x2,y2,color,size}
DRAW_FILL     = "draw_fill"      # {x,y,color}
DRAW_CLEAR    = "draw_clear"     # {}
DRAW_SNAPSHOT = "draw_snapshot"  # {data: base64-png}
WORD_CHOICE   = "word_choice"    # {word}
KICK_PLAYER   = "kick_player"    # {name}
CLOSE_ROOM    = "close_room"     # {}
START_GAME_REQ = "start_game_req"  # {} — owner requests game start

# ── Server → Client ───────────────────────────────────────────────────────────
PLAYER_LIST  = "player_list"   # {players:[…], owner, max_players}
JOINED       = "joined"        # {name}
GAME_START   = "game_start"    # {total_rounds}
ROUND_START  = "round_start"   # {drawer,hint,round,total_rounds,time}
CHOOSE_WORD  = "choose_word"   # {words:[w1,w2,w3]}
WORD_CHOSEN  = "word_chosen"   # {drawer}
HINT_UPDATE  = "hint_update"   # {hint}
TIMER_UPDATE = "timer_update"  # {remaining}
CHAT_MSG     = "chat_msg"      # {sender,text,guessed}
ROUND_END    = "round_end"     # {word, scores:[{name,score,gained}]}
GAME_END     = "game_end"      # {scores:[{name,score}]}
KICKED       = "kicked"        # {}
ROOM_CLOSED  = "room_closed"   # {}
ERROR        = "error"         # {text}
DISCONNECT   = "disconnect"    # internal client-side sentinel
CHECK_CODE   = "check_code"    # {room_code}  client→server (no JOIN, just a probe)
CODE_RESULT  = "code_result"   # {ok, error}  server→client


def pack(msg_type: str, **kwargs) -> bytes:
    msg = {"type": msg_type}
    msg.update(kwargs)
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def unpack(raw: bytes | str) -> dict:
    return json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
