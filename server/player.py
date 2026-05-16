import socket


class Player:
    def __init__(self, conn: socket.socket, addr, name: str = ""):
        self.conn = conn
        self.addr = addr
        self.name = name
        self.pfp_idx: int = 0
        self.score: int = 0
        self.is_drawing: bool = False
        self.has_guessed: bool = False  # this round

    def reset_round(self):
        self.is_drawing = False
        self.has_guessed = False

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
