import os

# --- LLM CONFIGURATION ---
# Supports latest Gemini models like "gemini-2.5-flash", "gemini-2.5-pro"
LLM_MODEL = os.getenv("AGENT_LLM_MODEL", "gemini-2.5-flash")

# --- TTS CONFIGURATIONS ---
# Available TTS Technologies/Engines: "chirp3", "journey", "neural2"
TTS_ENGINE = os.getenv("AGENT_TTS_ENGINE", "chirp3").lower()

TTS_PROFILES = {
    "chirp3": {
        "es": ("es-ES", "es-ES-Chirp3-HD-Leda"),
        "en": ("en-US", "en-US-Chirp3-HD-Zephyr"),
        "uk": ("uk-UA", "uk-UA-Chirp3-HD-Aoede"),
    },
    "journey": {
        "es": ("es-ES", "es-ES-Journey-F"),
        "en": ("en-US", "en-US-Journey-F"),
        # Fallback to Neural2 since Journey doesn't support 'uk' directly
        "uk": ("uk-UA", "uk-UA-Neural2-A"),
    },
    "neural2": {
        "es": ("es-ES", "es-ES-Neural2-F"),
        "en": ("en-US", "en-US-Neural2-F"),
        "uk": ("uk-UA", "uk-UA-Neural2-A"),
    }
}

# --- LANG & STT CONFIGURATIONS ---
LANG_NAME = {"es": "español", "en": "English", "uk": "українська"}
STT_LANG = {"es": "es-ES", "en": "en-US", "uk": "uk-UA"}


def get_tts_voice(locale: str, engine: str | None = None) -> tuple[str, str]:
    """
    Returns the (language_code, voice_name) for the requested TTS engine and locale.
    If `engine` is None, falls back to the env-configured TTS_ENGINE.
    Falls back to 'es' of the resolved engine if the requested locale is not configured.
    """
    eng = (engine or TTS_ENGINE).lower()
    eng = eng if eng in TTS_PROFILES else "chirp3"
    profiles = TTS_PROFILES[eng]

    voice_info = profiles.get(locale)
    if not voice_info:
        voice_info = profiles.get("es", ("es-ES", "es-ES-Chirp3-HD-Leda"))

    return voice_info
