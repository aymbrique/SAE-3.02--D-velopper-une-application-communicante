"""JSON UTF-8, un objet par ligne. Aucun appel socket dans ce module."""

import json
from uuid import UUID

MAX_LINE = 4096


def encode(message):
    return (json.dumps(message, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")


class Decoder:
    def __init__(self):
        self.buffer = b""

    def feed(self, data):
        self.buffer += data
        messages = []
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if len(line) > MAX_LINE:
                raise ValueError("Message trop long")
            try:
                message = json.loads(line)
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError("JSON invalide") from error
            if not isinstance(message, dict):
                raise ValueError("Objet JSON attendu")
            messages.append(message)
        if len(self.buffer) > MAX_LINE:
            raise ValueError("Message trop long")
        return messages


def validate(message):
    if message.get("type") == "ping":
        return message
    if message.get("type") != "etat":
        raise ValueError("Type de message inconnu")
    if message.get("id") not in ("01", "02") or message.get("etat") not in ("disponible", "occupe"):
        raise ValueError("Identifiant ou etat invalide")
    number = message.get("numero")
    if type(number) is not int or not 1 <= number < 2**63:
        raise ValueError("Numero de mise a jour invalide")
    try:
        if str(UUID(message["session"])) != message["session"]:
            raise ValueError("Session invalide")
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError("Session invalide") from error
    return message
