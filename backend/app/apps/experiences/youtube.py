"""Extração/validação de video id do YouTube — espelha byte a byte a lógica
de frontend/lib/youtube.ts (mesmos hosts, mesmos formatos de path, mesmo
regex de id) para que cliente e servidor nunca discordem sobre o que é um
link válido. Usado por
apps.experiences.serializers.ExperienceDraftSerializer.
validate_galaxy_live_music_url — nunca pelo music_url legado (esse aceita
Spotify/Apple Music também, e nunca teve essa validação de formato)."""

import re
from urllib.parse import urlparse, parse_qs

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}

# Formato real de video id do YouTube: sempre 11 caracteres.
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_youtube_video_id(url: str) -> str | None:
    """None quando `url` não é um link de vídeo do YouTube reconhecível.
    Aceita watch?v=, youtu.be/ e shorts/, com quaisquer parâmetros extras
    (t=, list=, si=, etc.) — esses são ignorados, só o id importa."""
    if not url:
        return None

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    hostname = parsed.hostname.lower() if parsed.hostname else ""
    if hostname not in _YOUTUBE_HOSTS:
        return None

    if hostname in ("youtu.be", "www.youtu.be"):
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate if _VIDEO_ID_PATTERN.match(candidate) else None

    if parsed.path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [None])[0]
        return candidate if candidate and _VIDEO_ID_PATTERN.match(candidate) else None

    shorts_match = re.match(r"^/shorts/([^/]+)/?$", parsed.path)
    if shorts_match:
        candidate = shorts_match.group(1)
        return candidate if _VIDEO_ID_PATTERN.match(candidate) else None

    return None
