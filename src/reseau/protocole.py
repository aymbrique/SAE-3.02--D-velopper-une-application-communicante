"""JSON UTF-8, un objet par ligne. Aucun appel socket dans ce module."""

import json
from uuid import UUID

TAILLE_LIGNE_MAX = 4096


def encoder(message):
    """Convertit un message en octets JSON UTF-8 terminés par un saut de ligne."""
    texte = json.dumps(message, ensure_ascii=True, separators=(",", ":"))
    texte += "\n"  # Fin d'un message.
    return texte.encode("utf-8")


class Decodeur:
    """Tampon qui reconstitue les messages JSON reçus par morceaux sur TCP."""

    def __init__(self):
        """Crée un tampon de réception vide."""
        self.tampon = b""

    def alimenter(self, donnees):
        """Ajoute les octets reçus et extrait les messages complets.

        Paramètres :
            donnees: Nouveaux octets reçus par la socket.

        Résultat :
            La liste des objets JSON complets ; les octets restants sont conservés.

        Exceptions :
            ValueError: Si un message est trop long, invalide ou différent d'un objet JSON.
        """
        # TCP peut livrer un message en plusieurs morceaux : garder le debut.
        self.tampon += donnees
        messages = []
        while b"\n" in self.tampon:
            ligne, self.tampon = self.tampon.split(b"\n", 1)
            if len(ligne) > TAILLE_LIGNE_MAX:
                raise ValueError("Message trop long")
            try:
                message = json.loads(ligne)
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError("JSON invalide") from error
            if not isinstance(message, dict):
                raise ValueError("Objet JSON attendu")
            messages.append(message)
        if len(self.tampon) > TAILLE_LIGNE_MAX:
            raise ValueError("Message trop long")
        return messages


def valider(message):
    """Vérifie les champs d'un message et le renvoie, ou lève ValueError."""
    if message.get("type") == "verification_liaison":
        return message
    if message.get("type") != "etat":
        raise ValueError("Type de message inconnu")
    if message.get("id") not in ("01", "02") or message.get("etat") not in ("disponible", "occupe"):
        raise ValueError("Identifiant ou etat invalide")
    numero = message.get("numero")
    if type(numero) is not int or not 1 <= numero < 2**63:
        raise ValueError("Numero de mise a jour invalide")
    try:
        if str(UUID(message["session"])) != message["session"]:
            raise ValueError("Session invalide")
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError("Session invalide") from error
    return message
