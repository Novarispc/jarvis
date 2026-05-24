"""
JARVIS Multilingual Support

Language detection → English translation → VISION → back-translation → Edge TTS

Supported languages: Hindi (hi), Tamil (ta), Telugu (te), Malayalam (ml),
                     Kannada (kn), Swedish (sv)

Dependencies (add to requirements.txt):
    langdetect>=1.0.9
    deep-translator>=1.11.4
"""
import logging
from typing import Optional

log = logging.getLogger("jarvis.multilingual")

# ---------------------------------------------------------------------------
# Language catalogue
# ---------------------------------------------------------------------------

LANGUAGES: dict[str, dict] = {
    "hi": {"name": "Hindi",     "edge_voice": "hi-IN-MadhurNeural"},
    "ta": {"name": "Tamil",     "edge_voice": "ta-IN-ValluvarNeural"},
    "te": {"name": "Telugu",    "edge_voice": "te-IN-MohanNeural"},
    "ml": {"name": "Malayalam", "edge_voice": "ml-IN-MidhunNeural"},
    "kn": {"name": "Kannada",   "edge_voice": "kn-IN-GaganNeural"},
    "sv": {"name": "Swedish",   "edge_voice": "sv-SE-MattiasNeural"},
}

DEFAULT_VOICE = "en-GB-RyanNeural"

# langdetect is probabilistic — add a minimum-length guard
_MIN_DETECT_CHARS = 10


def detect_language(text: str) -> Optional[str]:
    """Return ISO 639-1 language code, or None if detection fails / text too short."""
    if len(text.strip()) < _MIN_DETECT_CHARS:
        return None
    try:
        from langdetect import detect, LangDetectException  # type: ignore
        lang = detect(text)
        return lang
    except Exception as exc:
        log.debug(f"Language detection failed: {exc}")
        return None


def is_supported(lang_code: Optional[str]) -> bool:
    """True when lang_code maps to a non-English supported language."""
    if not lang_code:
        return False
    return lang_code.split("-")[0].lower() in LANGUAGES


def translate(text: str, source_lang: str, target_lang: str = "en") -> str:
    """Translate text via deep-translator (Google, free, no API key).

    Falls back to original text on any error so the pipeline never hard-fails.
    Supports both directions: native→English and English→native.
    """
    if not text.strip():
        return text
    src = source_lang.split("-")[0].lower()
    tgt = target_lang.split("-")[0].lower()
    if src == tgt:
        return text
    # Skip if neither side is a supported non-English language
    if src not in LANGUAGES and tgt not in LANGUAGES:
        return text
    try:
        from deep_translator import GoogleTranslator  # type: ignore
        translated = GoogleTranslator(source=src, target=tgt).translate(text)
        return translated or text
    except Exception as exc:
        log.warning(f"Translation {source_lang}→{target_lang} failed: {exc}")
        return text


def get_voice(lang_code: Optional[str]) -> str:
    """Return Edge TTS voice name for lang_code, falling back to default English voice."""
    if not lang_code:
        return DEFAULT_VOICE
    entry = LANGUAGES.get(lang_code.split("-")[0].lower())
    return entry["edge_voice"] if entry else DEFAULT_VOICE


def get_language_name(lang_code: Optional[str]) -> str:
    """Human-readable name for lang_code."""
    if not lang_code:
        return "English"
    entry = LANGUAGES.get(lang_code.split("-")[0].lower())
    return entry["name"] if entry else "English"
