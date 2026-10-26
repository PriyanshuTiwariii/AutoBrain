"""The LLM boundary: one small interface, and its OpenAI (Responses API) implementation.

The rest of the engine only knows `LLMClient`. Nothing here ever logs the buyer's text, and
exceptions are reduced to a kind and a status code before they leave this module, because an
SDK error message can quote what was sent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from . import config

logger = logging.getLogger("autobrain.llm")

REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")

ErrorKind = Literal["timeout", "api", "refusal", "incomplete", "bad_output"]


class LLMError(Exception):
    """A failed model call. `kind` and `status` are safe to log; the message is not shown or logged."""

    def __init__(self, kind: ErrorKind, status: int | None = None) -> None:
        super().__init__(kind)
        self.kind: ErrorKind = kind
        self.status = status


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "openai"
    api_key: str = ""
    primary_model: str = ""
    fallback_model: str = ""
    primary_effort: str = "none"
    fallback_effort: str = "low"
    timeout_seconds: float = 15.0
    max_output_tokens: int = 2000

    @classmethod
    def from_config(cls) -> "LLMSettings":
        return cls(
            provider=config.LLM_PROVIDER,
            api_key=config.OPENAI_API_KEY,
            primary_model=config.LLM_MODEL_PRIMARY,
            fallback_model=config.LLM_MODEL_FALLBACK,
            primary_effort=config.LLM_PRIMARY_REASONING_EFFORT,
            fallback_effort=config.LLM_FALLBACK_REASONING_EFFORT,
            timeout_seconds=config.LLM_TIMEOUT_SECONDS,
            max_output_tokens=config.LLM_MAX_OUTPUT_TOKENS,
        )

    def problem(self) -> str | None:
        """Why the LLM cannot be used, or None when it can. Never includes the key."""
        if self.provider != "openai":
            return f"LLM_PROVIDER={self.provider!r} is not supported (only 'openai')"
        if not self.api_key.strip():
            return "OPENAI_API_KEY is empty"
        if not self.primary_model:
            return "LLM_MODEL_PRIMARY is empty"
        for name, effort in (("primary", self.primary_effort), ("fallback", self.fallback_effort)):
            if effort not in REASONING_EFFORTS:
                return f"the {name} reasoning effort {effort!r} is not one of {', '.join(REASONING_EFFORTS)}"
        return None


class LLMClient(Protocol):
    def generate_json(
        self,
        *,
        model: str,
        effort: str,
        instructions: str,
        user_text: str,
        schema_name: str,
        schema: dict[str, Any],
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        """One structured-output call. Returns the parsed JSON object or raises LLMError."""
        ...


class OpenAIClient:
    """OpenAI Responses API with Structured Outputs (strict json_schema)."""

    def __init__(self, api_key: str) -> None:
        import openai  # imported here so the engine runs without the SDK when the LLM is off

        self._openai = openai
        # max_retries=0: the engine does its own single retry on the fallback model
        self._client = openai.OpenAI(api_key=api_key, max_retries=0)

    def generate_json(
        self,
        *,
        model: str,
        effort: str,
        instructions: str,
        user_text: str,
        schema_name: str,
        schema: dict[str, Any],
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        openai = self._openai
        try:
            response = self._client.with_options(timeout=timeout_seconds).responses.create(
                model=model,
                instructions=instructions,
                input=[{"role": "user", "content": user_text}],
                reasoning={"effort": effort},
                text={"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
                max_output_tokens=max_output_tokens,
                store=False,  # do not keep the buyer's text on OpenAI's side
            )
        except openai.APITimeoutError as exc:
            raise LLMError("timeout") from None
        except openai.APIStatusError as exc:
            raise LLMError("api", status=exc.status_code) from None
        except Exception:
            raise LLMError("api") from None

        if getattr(response, "status", None) == "incomplete":
            raise LLMError("incomplete")
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "message":
                continue
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "refusal":
                    raise LLMError("refusal")
        try:
            data = json.loads(response.output_text)
        except Exception:
            raise LLMError("bad_output") from None
        if not isinstance(data, dict):
            raise LLMError("bad_output")
        return data


def build_client(settings: LLMSettings) -> LLMClient | None:
    """The real client, or None when the LLM is not set up (the website then falls back to the form)."""
    reason = settings.problem()
    if reason:
        logger.info("LLM not available: %s", reason)
        return None
    try:
        return OpenAIClient(settings.api_key)
    except Exception as exc:  # SDK missing or broken: the engine must still start
        logger.warning("LLM not available: could not create the OpenAI client (%s)", type(exc).__name__)
        return None
