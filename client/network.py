import socket
import threading
import queue
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import pack, unpack, DISCONNECT


class NetworkClient:
    def __init__(self):
        self._sock: socket.socket | None = None
        self._queue: queue.Queue = queue.Queue()
        self._running = False

    def connect(self, host: str, port: int):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))
        self._running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def send(self, msg_type: str, **kwargs):
        if self._sock and self._running:
            try:
                self._sock.sendall(pack(msg_type, **kwargs))
            except OSError:
                self._queue.put({"type": DISCONNECT})

    def poll(self) -> list[dict]:
        """Return all queued messages since last poll."""
        msgs = []
        while True:
            try:
                msgs.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return msgs

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _recv_loop(self):
        buf = b""
        while self._running:
            try:
                data = self._sock.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            self._queue.put(unpack(line))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
            except OSError:
                break
        self._queue.put({"type": DISCONNECT})
