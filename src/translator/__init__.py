"""Translation modules for different translation services."""
from src.translator.llm_studio_translator import LLMStudioTranslator
from src.translator.libretranslate_translator import LibreTranslateTranslator

__all__ = ['LLMStudioTranslator', 'LibreTranslateTranslator']

