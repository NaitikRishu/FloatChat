from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["profiles", "compare_bgc", "nearest_floats", "trajectory", "summary"],
        },
        "parameter": {
            "type": "string",
            "enum": ["temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "backscatter"],
        },
        "region": {
            "type": "string",
            "enum": [
                "",
                "Arabian Sea",
                "Bay of Bengal",
                "Equatorial Indian Ocean",
                "Southern Indian Ocean",
                "Western Indian Ocean",
            ],
        },
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
        "use_lat_range": {"type": "boolean"},
        "lat_min": {"type": "number"},
        "lat_max": {"type": "number"},
        "use_lon_range": {"type": "boolean"},
        "lon_min": {"type": "number"},
        "lon_max": {"type": "number"},
        "use_point": {"type": "boolean"},
        "point_lat": {"type": "number"},
        "point_lon": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": [
        "intent",
        "parameter",
        "region",
        "start_date",
        "end_date",
        "use_lat_range",
        "lat_min",
        "lat_max",
        "use_lon_range",
        "lon_min",
        "lon_max",
        "use_point",
        "point_lat",
        "point_lon",
        "rationale",
    ],
}


@dataclass
class LLMService:
    provider: str
    api_key: str | None = None
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    reasoning_effort: str = "low"
    timeout_seconds: int = 45
    base_url: str = "https://api.openai.com/v1"
    ollama_url: str = "http://127.0.0.1:11434"

    @property
    def enabled(self) -> bool:
        if self.provider == "ollama":
            return True
        if self.provider in {"openai", "huggingface"}:
            return bool(self.api_key)
        return False

    def health_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider if self.enabled else "local-fallback",
            "enabled": self.enabled,
            "model": self.model if self.enabled else None,
            "reasoning_effort": self.reasoning_effort if self.enabled else None,
        }

    def plan_query(
        self,
        *,
        question: str,
        selected_point: tuple[float, float] | None,
        retrieval: list[dict[str, Any]],
        latest_catalog_date: str | None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        prompt_payload = {
            "question": question,
            "selected_point": selected_point,
            "latest_catalog_date": latest_catalog_date,
            "retrieval_context": [
                {
                    "title": item["title"],
                    "kind": item["kind"],
                    "content": item["content"],
                }
                for item in retrieval[:3]
            ],
        }
        system_prompt = (
            "You are planning oceanographic database queries for an ARGO float analytics app. "
            "Return only a valid JSON object that maps the user request into one of the supported intents. "
            "Use empty strings when a region or date is not specified. "
            "If the user asks for nearest floats, set use_point true and use selected_point if available. "
            "If the user says near the equator, use a latitude range around -5 to 5."
        )
        response = self._text_generation(
            system_prompt=system_prompt,
            user_payload=prompt_payload,
            json_mode=True,
            max_output_tokens=600,
        )
        text = self._extract_text(response)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def generate_answer(
        self,
        *,
        question: str,
        result: dict[str, Any],
        retrieval: list[dict[str, Any]],
    ) -> str | None:
        if not self.enabled:
            return None

        answer_payload = {
            "question": question,
            "intent": result.get("intent"),
            "parameter": result.get("parameter"),
            "summary": result.get("summary"),
            "sql": result.get("sql"),
            "top_rows": result.get("rows") or result.get("series") or result.get("profiles") or result.get("stats"),
            "retrieval_context": [
                {
                    "title": item["title"],
                    "kind": item["kind"],
                    "content": item["content"],
                }
                for item in retrieval[:3]
            ],
        }
        response = self._text_generation(
            system_prompt=(
                "You are an ocean data analyst. Write a concise, grounded answer for the user. "
                "Use only the supplied SQL result summary and retrieval context. "
                "Do not invent numbers. Keep the answer to 2 to 4 sentences."
            ),
            user_payload=answer_payload,
            json_mode=False,
            max_output_tokens=220,
        )
        return self._extract_text(response)

    def _text_generation(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        json_mode: bool,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        if self.provider == "ollama":
            return self._ollama_chat(
                system_prompt=system_prompt,
                user_payload=user_payload,
                json_mode=json_mode,
            )
        return self._responses_create(
            {
                "model": self.model,
                "reasoning": {"effort": self.reasoning_effort},
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": json.dumps(user_payload)}],
                    },
                ],
                "text": (
                    {
                        "format": {
                            "type": "json_schema",
                            "name": "argo_query_plan",
                            "strict": True,
                            "schema": PLAN_SCHEMA,
                        }
                    }
                    if json_mode
                    else None
                ),
                "max_output_tokens": max_output_tokens,
            }
        )

    def _responses_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("API key is not configured for this provider.")
        clean_payload = {key: value for key, value in payload.items() if value is not None}
        http_request = request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(clean_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.provider} API error {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not reach {self.provider} API: {exc.reason}") from exc

    def _ollama_chat(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        json_mode: bool,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        }
        if json_mode:
            payload["format"] = "json"
        http_request = request.Request(
            f"{self.ollama_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                return {"output_text": body.get("message", {}).get("content", "")}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ollama API error {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not reach ollama API: {exc.reason}") from exc

    def _extract_text(self, response: dict[str, Any]) -> str | None:
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        for item in response.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
                refusal = content.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    return refusal.strip()
        return None


OpenAIService = LLMService
