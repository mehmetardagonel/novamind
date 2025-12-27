"""
Translation Service for Email Classification

Provides Turkish → English translation support for ML model classification.
Uses googletrans for translation and langdetect for language detection.
Implements in-memory caching to avoid repeated API calls.
"""

import hashlib
import logging
from typing import Dict, Optional
from googletrans import Translator
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating emails before ML classification"""

    def __init__(self):
        """Initialize translation service with caching"""
        self.translator = Translator()
        self.cache = {}  # In-memory cache: {content_hash: translated_text}
        logger.info("✅ Translation Service initialized")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text hash"""
        return hashlib.md5(text.encode('utf-8', errors='ignore')).hexdigest()

    def detect_language(self, text: str) -> str:
        """
        Detect language of text

        Args:
            text: Text to detect language for

        Returns:
            Language code (e.g., 'tr', 'en', 'ar')
            Returns 'en' if detection fails
        """
        if not text or not text.strip():
            return 'en'

        try:
            # Use langdetect to identify language
            lang = detect(text)
            logger.debug(f"Detected language: {lang}")
            return lang
        except LangDetectException as e:
            logger.warning(f"Language detection failed: {e}, defaulting to English")
            return 'en'
        except Exception as e:
            logger.error(f"Unexpected error in language detection: {e}")
            return 'en'

    def translate_to_english(self, text: str, source_lang: str = 'tr') -> str:
        """
        Translate text to English with caching

        Args:
            text: Text to translate
            source_lang: Source language code (default: 'tr' for Turkish)

        Returns:
            Translated English text, or original if translation fails
        """
        if not text or not text.strip():
            return text

        # Check cache first
        cache_key = self._get_cache_key(text)
        if cache_key in self.cache:
            logger.debug(f"Translation cache hit for text hash: {cache_key[:8]}...")
            return self.cache[cache_key]

        try:
            # Translate using googletrans
            translated = self.translator.translate(text, src=source_lang, dest='en')
            translated_text = translated.text

            # Cache the result
            self.cache[cache_key] = translated_text
            logger.debug(f"Translated ({source_lang} → en): {text[:50]}... → {translated_text[:50]}...")

            return translated_text

        except Exception as e:
            logger.warning(f"Translation failed for text: {text[:50]}... Error: {e}")
            logger.warning("Falling back to original text")
            return text

    def translate_email(self, subject: str, body: str) -> Dict[str, str]:
        """
        Translate email subject and body

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Dictionary with translated subject and body
            {
                'subject': translated_subject,
                'body': translated_body,
                'detected_lang': language_code
            }
        """
        # Detect language from combined text
        combined_text = f"{subject} {body}".strip()
        detected_lang = self.detect_language(combined_text)

        # If already English, return as-is
        if detected_lang == 'en':
            return {
                'subject': subject,
                'body': body,
                'detected_lang': 'en'
            }

        # Translate subject and body separately
        try:
            translated_subject = self.translate_to_english(subject, source_lang=detected_lang) if subject else ''
            translated_body = self.translate_to_english(body, source_lang=detected_lang) if body else ''

            return {
                'subject': translated_subject,
                'body': translated_body,
                'detected_lang': detected_lang
            }

        except Exception as e:
            logger.error(f"Email translation failed: {e}")
            return {
                'subject': subject,
                'body': body,
                'detected_lang': detected_lang
            }

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.cache),
            'cached_translations': len(self.cache)
        }


# Singleton instance
_translation_service: Optional[TranslationService] = None


def get_translation_service() -> TranslationService:
    """
    Get singleton translation service instance

    Returns:
        TranslationService instance
    """
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service
