"""Translation modules for different translation services."""
from src.translator.llm_studio_translator import LLMStudioTranslator
from src.translator.libretranslate_translator import LibreTranslateTranslator
from src.translator.ollama_translator import OllamaTranslator
from src.translator.chatgpt_translator import ChatGPTTranslator
from src.translator.gemini_translator import GeminiTranslator
from src.translator.mistral_translator import MistralTranslator

__all__ = ['LLMStudioTranslator', 'LibreTranslateTranslator', 'OllamaTranslator', 'ChatGPTTranslator', 'GeminiTranslator', 'MistralTranslator']

