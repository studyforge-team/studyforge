"""Token Factory client: fallback chain, retries, deadlines, cost log, JSON repair.

The openai SDK's own retries are off (max_retries=0) so that every attempt is
logged, every wait respects the solve's deadline, and 4xx errors are never retried.
"""

import asyncio
import json
import os
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, TypeVar, cast

import httpx
import openai
from pydantic import BaseModel

from app.llm.cost import BudgetGuard, CallRecord, CostRecorder, NoBudgetGuard, price
from app.llm.errors import (
    DeadlineExceeded,
    JSONRepairFailed,
    LLMAuthError,
    LLMRequestError,
    ModelUnavailable,
)
from app.llm.reasoning import extract_json, strip_reasoning
from app.llm.registry import Registry, ResolvedModel

Message = dict[str, Any]
T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
BACKOFF_BASE_S = 0.5
BACKOFF_CAP_S = 8.0
RETRY_AFTER_CAP_S = 30.0
JSON_INSTRUCTION = (
    "Reply with only one JSON object that matches this JSON Schema, no other text:\n"
)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text from the model; the agent validates it


@dataclass(frozen=True)
class LLMResult:
    text: str  # reasoning already stripped
    reasoning: str | None
    tool_calls: list[ToolCall]
    model_id: str
    role: str
    cost_usd: float  # every attempt of this call; unpriced models count as 0
    attempts: int


class LLMClient:
    def __init__(
        self,
        registry: Registry,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        recorder: CostRecorder | None = None,
        budget: BudgetGuard | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.registry = registry
        key = api_key or os.environ.get(registry.api_key_env)
        self._has_key = bool(key)
        self._openai = openai.AsyncOpenAI(
            base_url=registry.base_url,
            api_key=key or "unset",
            max_retries=0,
            http_client=http_client,
        )
        self.recorder = recorder
        self.budget = budget or NoBudgetGuard()
        self.clock = clock
        self.sleep = sleep
        self.rng = rng

    async def chat(
        self,
        role: str,
        messages: list[Message],
        *,
        deadline: float | None = None,
        solve_id: str | None = None,
        reasoning: bool | None = None,
    ) -> LLMResult:
        """deadline is an absolute time on this client's clock (time.monotonic)."""
        return await self._complete(role, messages, deadline, solve_id, reasoning, {})

    async def chat_tools(
        self,
        role: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        deadline: float | None = None,
        solve_id: str | None = None,
        tool_choice: str = "auto",
    ) -> LLMResult:
        extra = {"tools": tools, "tool_choice": tool_choice}
        return await self._complete(role, messages, deadline, solve_id, None, extra)

    async def chat_json(
        self,
        role: str,
        messages: list[Message],
        schema: type[T],
        *,
        deadline: float | None = None,
        solve_id: str | None = None,
    ) -> tuple[T, LLMResult]:
        """Reasoning off, reasoning text stripped, validated, repaired at most once."""
        convo = _with_schema(messages, schema)
        first = await self._complete(role, convo, deadline, solve_id, False, {})
        try:
            return _validate(schema, first.text), first
        except ValueError as err:
            repair = [
                *convo,
                {"role": "assistant", "content": first.text},
                {
                    "role": "user",
                    "content": f"Your reply was not valid JSON for the schema "
                    f"({str(err)[:500]}). Reply with only the corrected JSON object.",
                },
            ]
        second = await self._complete(role, repair, deadline, solve_id, False, {})
        total = replace(
            second,
            cost_usd=first.cost_usd + second.cost_usd,
            attempts=first.attempts + second.attempts,
        )
        try:
            return _validate(schema, second.text), total
        except ValueError as err:
            raise JSONRepairFailed(
                f"invalid JSON after repair: {err}", second.text
            ) from err

    async def vision(
        self,
        image_url: str,
        prompt: str,
        *,
        deadline: float | None = None,
        solve_id: str | None = None,
    ) -> LLMResult:
        """image_url is usually a data: URL (JPEG, longest side ~1600 px)."""
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        messages = [{"role": "user", "content": content}]
        return await self._complete("vision", messages, deadline, solve_id, None, {})

    async def _complete(
        self,
        role: str,
        messages: list[Message],
        deadline: float | None,
        solve_id: str | None,
        reasoning: bool | None,
        extra: dict[str, Any],
    ) -> LLMResult:
        if not self._has_key:
            raise LLMAuthError(f"{self.registry.api_key_env} is not set")
        spec = self.registry.roles[role]
        params: dict[str, Any] = {
            k: v
            for k in ("temperature", "top_p", "max_tokens")
            if (v := getattr(spec, k)) is not None
        }
        params.update(extra)
        think = spec.reasoning if reasoning is None else reasoning
        cost, attempts, last = 0.0, 0, ""
        for model in self.registry.chain(role):
            for retry in range(MAX_RETRIES + 1):
                timeout = self._timeout(spec.timeout_s, deadline)
                await self.budget.check(role, model.id)
                attempts += 1
                start = self.clock()
                try:
                    resp = await self._openai.chat.completions.create(
                        model=model.id,
                        messages=cast(Any, messages),
                        timeout=timeout,
                        extra_body={"chat_template_kwargs": {"enable_thinking": think}},
                        **params,
                    )
                except openai.APIError as exc:
                    last = _describe(exc)
                    await self._log(role, model, solve_id, start, last, 0, 0)
                    if isinstance(
                        exc, openai.AuthenticationError | openai.PermissionDeniedError
                    ):
                        raise LLMAuthError(last) from exc
                    if isinstance(exc, openai.NotFoundError):
                        break  # model not served: next in chain, no retry
                    if not _retryable(exc):
                        raise LLMRequestError(last) from exc
                    if retry == MAX_RETRIES:
                        break
                    await self._wait(retry, exc, deadline)
                    continue
                usage = resp.usage
                pt, ct = (
                    (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
                )
                row_cost = await self._log(role, model, solve_id, start, None, pt, ct)
                cost += row_cost or 0.0
                msg = resp.choices[0].message
                extra_fields = msg.model_extra or {}
                return LLMResult(
                    text=strip_reasoning(msg.content),
                    reasoning=extra_fields.get("reasoning_content")
                    or extra_fields.get("reasoning"),
                    tool_calls=[
                        ToolCall(c.id, c.function.name, c.function.arguments)
                        for c in msg.tool_calls or []
                        if isinstance(
                            c, openai.types.chat.ChatCompletionMessageFunctionToolCall
                        )
                    ],
                    model_id=model.id,
                    role=role,
                    cost_usd=cost,
                    attempts=attempts,
                )
        raise ModelUnavailable(f"role '{role}': every model failed (last: {last})")

    def _timeout(self, role_timeout: float, deadline: float | None) -> float:
        if deadline is None:
            return role_timeout
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise DeadlineExceeded("solve time budget used up")
        return min(role_timeout, remaining)

    async def _wait(
        self, retry: int, exc: openai.APIError, deadline: float | None
    ) -> None:
        delay = _retry_after(exc)
        if delay is None:
            delay = (
                min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2**retry)
                + self.rng() * BACKOFF_BASE_S
            )
        if deadline is not None and self.clock() + delay >= deadline:
            raise DeadlineExceeded(f"no time left to retry after {_describe(exc)}")
        await self.sleep(delay)

    async def _log(
        self,
        role: str,
        model: ResolvedModel,
        solve_id: str | None,
        start: float,
        error: str | None,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float | None:
        cost = price(model, prompt_tokens, completion_tokens)
        if self.recorder is not None:
            await self.recorder.record(
                CallRecord(
                    role=role,
                    model_id=model.id,
                    ok=error is None,
                    error=error,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                    latency_ms=int((self.clock() - start) * 1000),
                    solve_id=solve_id,
                )
            )
        return cost


def _retryable(exc: openai.APIError) -> bool:
    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        return True
    status = getattr(exc, "status_code", 0)
    return status in (408, 429) or status >= 500


def _retry_after(exc: openai.APIError) -> float | None:
    if not isinstance(exc, openai.APIStatusError):
        return None
    headers = exc.response.headers
    try:
        if "retry-after-ms" in headers:
            return min(RETRY_AFTER_CAP_S, float(headers["retry-after-ms"]) / 1000)
        if "retry-after" in headers:
            return min(RETRY_AFTER_CAP_S, float(headers["retry-after"]))
    except ValueError:  # HTTP-date form: fall back to backoff
        return None
    return None


def _describe(exc: openai.APIError) -> str:
    if isinstance(exc, openai.APITimeoutError):
        return "timeout"
    if isinstance(exc, openai.APIStatusError):
        return f"status {exc.status_code}"
    return type(exc).__name__


def _with_schema(messages: list[Message], schema: type[BaseModel]) -> list[Message]:
    instruction = JSON_INSTRUCTION + json.dumps(schema.model_json_schema())
    if messages and messages[0].get("role") == "system":
        head = {**messages[0], "content": f"{messages[0]['content']}\n\n{instruction}"}
        return [head, *messages[1:]]
    return [{"role": "system", "content": instruction}, *messages]


def _validate(schema: type[T], text: str) -> T:
    return schema.model_validate(extract_json(text))  # ValidationError is a ValueError
