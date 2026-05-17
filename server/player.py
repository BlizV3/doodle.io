import socket


class Player:
    # Store the socket connection, address, and name; initialize all game-state flags.
    def __init__(self, conn: socket.socket, addr, name: str = ""):
        self.conn = conn
        self.addr = addr
        self.name = name
        self.pfp_idx: int = 0
        self.score: int = 0
        self.is_drawing: bool = False
        self.has_guessed: bool = False  # this round

    # Clear the per-round drawing and guessed flags at the start of each new turn.
    def reset_round(self):
        self.is_drawing = False
        self.has_guessed = False

    # Serialize the player's state into a dict for PLAYER_LIST broadcast messages.
    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "pfp_idx":     self.pfp_idx,
            "score":       self.score,
            "is_drawing":  self.is_drawing,
            "has_guessed": self.has_guessed,
        }

    def __repr__(self):
        return f"<Player {self.name!r} score={self.score}>"
