# providers/llm_client.py
import os
import json
import requests
from typing import Optional

class LLMClient:
    """
    LLM client multi-provider (fallback):
    - Prioriza PIAPI (PIAPI_API_KEY)
    - Depois GROQ (GROQ_API_KEY)
    - Depois DEEPSEEK (DEEPSEEK_API_KEY)
    - Depois OPENAI (OPENAI_API_KEY) if present

    generate(...) returns a string result.
    """

    def __init__(self, provider: Optional[str] = None):
        # provider hint may be 'piapi','groq','deepseek','openai'
        self.provider_hint = (provider or "").lower() if provider else None

        # read env keys
        self.piapi_key = os.environ.get("PIAPI_API_KEY", "").strip()
        self.groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

        # decide active provider
        self.active_provider = self._select_provider()
        if not self.active_provider:
            raise RuntimeError(
                "Nenhuma chave encontrada para provedores. Defina ao menos PIAPI_API_KEY (recomendado) ou as demais."
            )

    def _select_provider(self) -> Optional[str]:
        # if user hints provider and key exists, use it
        hint = self.provider_hint
        if hint == "piapi" and self.piapi_key:
            return "piapi"
        if hint == "groq" and self.groq_key:
            return "groq"
        if hint == "deepseek" and self.deepseek_key:
            return "deepseek"
        if hint == "openai" and self.openai_key:
            return "openai"

        # fallback order explicit
        if self.piapi_key:
            return "piapi"
        if self.groq_key:
            return "groq"
        if self.openai_key:
            return "openai"
        if self.deepseek_key:
            return "deepseek"
        return None

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.4, max_tokens: int = 1000) -> str:
        """
        Minimal implementation. Replace with real SDK calls for production.
        Returns text string.
        """

        # Basic payload for any provider; adapt per provider as needed.
        if self.active_provider == "piapi":
            # Placeholder: if you have a real PIAPI endpoint/SDK, replace this block.
            # We simply return a composed message to avoid failing.
            return f"(PIAPI placeholder) Provider: PIAPI. System: {system_prompt[:200]} ... User prompt preview: {user_prompt[:400]}"
        if self.active_provider == "groq":
            return f"(GROQ placeholder) Provider: GROQ. System: {system_prompt[:200]} ... User prompt preview: {user_prompt[:400]}"
        if self.active_provider == "openai":
            return f"(OPENAI placeholder) Provider: OpenAI. System: {system_prompt[:200]} ... User prompt preview: {user_prompt[:400]}"
        if self.active_provider == "deepseek":
            return f"(DEEPSEEK placeholder) Provider: DeepSeek. System: {system_prompt[:200]} ... User prompt preview: {user_prompt[:400]}"

        # fallback
        return "(LLM placeholder) Nenhum provider ativo corretamente configurado."
