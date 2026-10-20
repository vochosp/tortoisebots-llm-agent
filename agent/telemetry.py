"""Listens to the TortoiseBots telemetry (UDP, JSON datagrams) for one bot.

The server sends a snapshot of every bot each 2 s (BOT_BATCH), activity
events such as deaths or loot (BOT_EVENTS) and anomalies such as STUCK
(ANOMALY). Enable it with AiPlayerbot.Observability = 1 in aiplayerbot.conf.
"""

import json
import socket
import threading
import time


class Telemetry:
    def __init__(self, bot_name, port):
        self.bot_name = bot_name.lower()
        self.port = port
        self.state = None          # latest snapshot of the bot (dict)
        self.state_time = 0.0      # time.time() of that snapshot
        self.money = None          # copper, only known from activity events
        self._events = []          # events and anomalies not yet taken
        self._lock = threading.Lock()

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", self.port))
        threading.Thread(target=self._listen, args=(sock,), daemon=True).start()

    def take_events(self):
        """Returns the events received since the last call."""
        with self._lock:
            events, self._events = self._events, []
        return events

    def _is_our_bot(self, name):
        return (name or "").lower() == self.bot_name

    def _listen(self, sock):
        while True:
            data, _ = sock.recvfrom(65535)
            try:
                msg = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            kind = msg.get("type")
            with self._lock:
                if kind == "BOT_BATCH":
                    for bot in msg.get("bots", []):
                        if self._is_our_bot(bot.get("name")):
                            self.state = bot
                            self.state_time = time.time()
                elif kind == "BOT_EVENTS":
                    for event in msg.get("events", []):
                        if self._is_our_bot(event.get("bot")):
                            self.money = event.get("money", self.money)
                            self._events.append({"kind": "event", **event})
                elif kind is not None and self._is_our_bot(msg.get("bot")):
                    # ANOMALY datagrams carry the bot name at the top level.
                    self._events.append({"kind": kind, **msg})
