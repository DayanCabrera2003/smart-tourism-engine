"""T061 -- Cliente LLM: abstraccion sobre Gemini y Ollama."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

__all__ = ["LLMClient"]

_GEMINI_MODEL = "gemini-2.5-flash"


def _build_genai_client(api_key: str) -> Any:
    from google import genai
    return genai.Client(api_key=api_key)


class LLMClient:
    """Abstrae el acceso al LLM.

    Soporta dos proveedores via el parametro ``provider``:
    - ``"gemini"``: usa google-genai SDK con gemini-2.5-flash.
    - ``"ollama"``: usa httpx contra la API REST de Ollama.
    """

    def __init__(
        self,
        *,
        provider: str = "gemini",
        api_key: str | None = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3",
    ) -> None:
        if provider not in ("gemini", "ollama"):
            raise ValueError(f"provider debe ser 'gemini' u 'ollama', se recibio: {provider!r}")
        self._provider = provider
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._genai_client = None

        if provider == "gemini":
            if not api_key:
                raise RuntimeError(
                    "LLM_API_KEY es obligatoria cuando LLM_PROVIDER=gemini. "
                    "Anadela al archivo .env."
                )
            self._genai_client = _build_genai_client(api_key)

    def generate(self, prompt: str) -> str:
        """Devuelve la respuesta completa como string."""
        if self._provider == "gemini":
            response = self._genai_client.models.generate_content(
                model=_GEMINI_MODEL,
                contents=prompt,
            )
            return response.text or ""
        return self._ollama_generate(prompt)

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Itera sobre fragmentos de texto a medida que el LLM los produce."""
        if self._provider == "gemini":
            for chunk in self._genai_client.models.generate_content_stream(
                model=_GEMINI_MODEL,
                contents=prompt,
            ):
                if chunk.text:
                    yield chunk.text
        else:
            yield from self._ollama_stream(prompt)

    def _ollama_generate(self, prompt: str) -> str:
        import httpx
        response = httpx.post(
            f"{self._ollama_url}/api/generate",
            json={"model": self._ollama_model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def _ollama_stream(self, prompt: str) -> Iterator[str]:
        import json

        import httpx
        with httpx.stream(
            "POST",
            f"{self._ollama_url}/api/generate",
            json={"model": self._ollama_model, "prompt": prompt, "stream": True},
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if token := data.get("response"):
                        yield token
                    if data.get("done"):
                        break
