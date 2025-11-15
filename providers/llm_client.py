import os
import requests


class LLMClient:
    """
    Cliente LLM com fallback automático:
    -> PIAPI (padrão)
    -> Groq
    -> OpenAI
    -> DeepSeek
    """

    def __init__(self, provider: str | None = None):
        self.order = os.getenv("LLM_FALLBACK_ORDER", "piapi,groq,openai,deepseek").split(",")
        self.default_provider = provider or os.getenv("LLM_PROVIDER", "piapi")
        self.active_provider = None

    # ------------------------
    # Chamadas de providers
    # ------------------------

    def _piapi(self, system_prompt, user_prompt, temperature, max_tokens):
        api_key = os.getenv("PIAPI_API_KEY")
        if not api_key:
            raise RuntimeError("PIAPI_API_KEY faltando")
        url = "https://api.piapi.ai/v1/chat/completions"
        payload = {
            "model": os.getenv("PIAPI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _groq(self, system_prompt, user_prompt, temperature, max_tokens):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY faltando")
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _openai(self, system_prompt, user_prompt, temperature, max_tokens):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY faltando")
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _deepseek(self, system_prompt, user_prompt, temperature, max_tokens):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY faltando")
        url = "https://api.deepseek.com/v1/chat/completions"
        payload = {
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ------------------------
    # Lógica de fallback
    # ------------------------

    def generate(self, system_prompt, user_prompt, temperature=0.4, max_tokens=1800):
        last_error = None

        for provider in self.order:
            try:
                self.active_provider = provider

                if provider == "piapi":
                    return self._piapi(system_prompt, user_prompt, temperature, max_tokens)

                if provider == "groq":
                    return self._groq(system_prompt, user_prompt, temperature, max_tokens)

                if provider == "openai":
                    return self._openai(system_prompt, user_prompt, temperature, max_tokens)

                if provider == "deepseek":
                    return self._deepseek(system_prompt, user_prompt, temperature, max_tokens)

            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"Falha em todos os providers. Último erro: {last_error}")
