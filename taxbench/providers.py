"""Where answers come from: a model behind an API, or a stand-in for testing the pipeline."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """Any chat completions endpoint that speaks the OpenAI wire format."""

    def __init__(self, model: str, base_url: str, api_key_env: str = "TAXBENCH_API_KEY", timeout: int = 120):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        self.timeout = timeout
        if not self.api_key:
            raise ProviderError(f"set the {api_key_env} environment variable")

    def complete(self, system: str, user: str, case: dict | None = None) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
            return payload["choices"][0]["message"]["content"] or ""
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as exc:
            raise ProviderError(f"request failed: {exc}") from exc


class OracleProvider:
    """Returns the expected answer. Used to prove the runner and grader agree with the cases."""

    def complete(self, system: str, user: str, case: dict | None = None) -> str:
        return json.dumps(case["expected"])


class StaleProvider:
    """Returns the outdated answer where a case records one. Simulates a model on old rules."""

    def complete(self, system: str, user: str, case: dict | None = None) -> str:
        answer = dict(case["expected"])
        answer.update(case.get("stale_answer") or {})
        return json.dumps(answer)
