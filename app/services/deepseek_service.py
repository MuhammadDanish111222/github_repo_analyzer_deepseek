from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.exceptions import LLMAnalysisError
from app.schemas import SelectedSourceFile

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a senior application security engineer and backend code reviewer.
Analyze the provided primary source code file for potential bugs, security vulnerabilities, unsafe patterns, and reliability risks.
Return JSON only. Do not include markdown, comments, code fences, or explanations outside JSON.
The JSON must contain exactly these keys:
{
  "vulnerabilities_found": ["clear finding 1", "clear finding 2"],
  "suggestions": "brief structural or optimization advice"
}
Rules:
- Include concrete findings only.
- Mention the risk and affected pattern when possible.
- If no clear issue is found, return an empty vulnerabilities_found list.
- Keep suggestions brief and practical.
""".strip()


class LLMStructuredOutput(BaseModel):
    vulnerabilities_found: list[str] = Field(default_factory=list)
    suggestions: str = "No structural suggestions provided."


class DeepSeekAnalyzerService:
    """Analyze source code with the DeepSeek Chat Completions API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze_source(self, source_file: SelectedSourceFile) -> LLMStructuredOutput:
        endpoint = str(self.settings.deepseek_base_url).rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        user_prompt = self._build_user_prompt(source_file)
        payload: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            # Thinking mode improves code-review quality. Reasoning tokens are internal
            # to DeepSeek and are not returned by this API, keeping the assessment
            # response clean and matching the required JSON contract.
            "max_tokens": 2500,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": self.settings.deepseek_thinking_type},
            "reasoning_effort": self.settings.deepseek_reasoning_effort,
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("DeepSeek request timed out")
            raise LLMAnalysisError("DeepSeek analysis timed out. Please try again.") from exc
        except httpx.HTTPError as exc:
            logger.exception("DeepSeek HTTP request failed")
            raise LLMAnalysisError() from exc

        if response.status_code == 401:
            raise LLMAnalysisError("DeepSeek API authentication failed. Check DEEPSEEK_API_KEY.")
        if response.status_code == 429:
            raise LLMAnalysisError("DeepSeek API rate limit reached. Please try again later.")
        if response.status_code >= 400:
            logger.warning("DeepSeek API failed: %s %s", response.status_code, response.text[:500])
            raise LLMAnalysisError()

        try:
            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Unexpected DeepSeek response shape: %s", response.text[:500])
            raise LLMAnalysisError("DeepSeek returned an unexpected response format.") from exc

        return self._parse_llm_json(raw_content)

    def _build_user_prompt(self, source_file: SelectedSourceFile) -> str:
        return f"""
Repository: {source_file.owner}/{source_file.repo}
Repository name: {source_file.repo_name}
Branch: {source_file.default_branch}
Selected primary source file: {source_file.path}

Analyze this code:

```text
{source_file.code}
```
""".strip()

    def _parse_llm_json(self, raw_content: str) -> LLMStructuredOutput:
        try:
            parsed = json.loads(raw_content)
            return LLMStructuredOutput.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Could not parse DeepSeek JSON output: %s", raw_content[:500])
            raise LLMAnalysisError("DeepSeek returned invalid JSON. Please retry the request.") from exc
