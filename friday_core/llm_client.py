"""Gemini LLM Client — via endpoint OpenAI-compatible do Google."""

from __future__ import annotations
import json
import os
import time
from typing import Any, Optional
import httpx


DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


class GeminiError(Exception):
    def __init__(self, message: str, *, status: Optional[int] = None,
                 retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None,
                 model: str = DEFAULT_MODEL, timeout: float = DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or ""
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def health(self) -> bool:
        if not self.is_configured():
            return False
        try:
            r = self.chat([{"role": "user", "content": "OK"}],
                          max_tokens=5, timeout=10.0)
            return bool(r)
        except Exception:
            return False

    def chat(self, messages: list[dict[str, str]], *, system: Optional[str] = None,
             model: Optional[str] = None, temperature: float = 0.2,
             max_tokens: int = 1024, response_format: Optional[dict[str, Any]] = None,
             timeout: Optional[float] = None) -> str:
        if not self.is_configured():
            raise GeminiError("GEMINI_API_KEY não configurada", retryable=False)

        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout or self.timeout) as c:
                    r = c.post(self.endpoint, json=payload, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    return data["choices"][0]["message"]["content"]

                try:
                    err_body = r.json()
                    err_msg = err_body.get("error", {}).get("message", r.text)
                    if isinstance(err_msg, list):
                        err_msg = err_msg[0].get("error", {}).get("message", str(err_msg))
                except Exception:
                    err_msg = r.text

                retryable = r.status_code in (429, 500, 502, 503, 504)
                if r.status_code == 429 and attempt < self.max_retries:
                    wait = 2.0 * attempt
                    time.sleep(wait)
                    continue
                raise GeminiError(
                    f"Gemini API {r.status_code}: {err_msg}",
                    status=r.status_code, retryable=retryable,
                )
            except httpx.HTTPError as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                raise GeminiError(f"HTTP error: {e}", retryable=True) from e
            except GeminiError as e:
                if e.retryable and attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                raise

        raise GeminiError(f"Failed after retries: {last_err}", retryable=False)

    def chat_json(self, messages: list[dict[str, str]], *, system: Optional[str] = None,
                  model: Optional[str] = None, temperature: float = 0.2,
                  max_tokens: int = 2048, timeout: Optional[float] = None) -> Any:
        text = self.chat(
            messages, system=system, model=model, temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}, timeout=timeout,
        )
        return json.loads(text)
