from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.clients.base import BaseLLMClient, LLMResponse
from app.router.smart_router import RoutingDecision, SmartAIRouter

logger = structlog.get_logger(__name__)


class SmartRouterClient(BaseLLMClient):
    """Unified LLM Client that intelligently delegates generation to Local LLM or Frontier Gemini."""

    provider_name = "smart_router"

    def __init__(
        self,
        frontier_client: BaseLLMClient,
        local_client: BaseLLMClient,
        router: SmartAIRouter,
    ) -> None:
        self.frontier_client = frontier_client
        self.local_client = local_client
        self.router = router
        if getattr(self.router, "local_client", None) is None:
            self.router.local_client = self.local_client

    def classify(
        self,
        prompt: str,
        *,
        strategy_override: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Classify a prompt using the underlying SmartAIRouter."""
        return self.router.classify(prompt, strategy_override=strategy_override, context=context)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        strategy_override: str | None = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Dynamically routes generate request to Local LLM or Frontier Gemini with automatic fallback."""
        history = chat_history or (context.get("chat_history") if context else None)
        if hasattr(self.router, "decide"):
            decision = await self.router.decide(prompt, strategy_override=strategy_override, context=context)
        else:
            decision = self.router.classify(prompt, strategy_override=strategy_override, context=context)
        logger.info(
            "smart_router_decision",
            target=decision.target,
            strategy=decision.strategy.value,
            complexity_score=decision.complexity_score,
            reason=decision.reason,
        )

        start = time.perf_counter()
        if decision.target == "local":
            try:
                response = await self.local_client.generate(
                    prompt,
                    system_prompt=system_prompt,
                    chat_history=history,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    context=context,
                )
                self.router.record_local_success()
                response.metadata.update(
                    {
                        "routed_to": "local",
                        "routing_strategy": decision.strategy.value,
                        "complexity_score": decision.complexity_score,
                        "routing_reason": decision.reason,
                        "fallback_triggered": False,
                    }
                )
                return response
            except Exception as e:
                self.router.record_local_failure(e)
                if not self.router.fallback_enabled:
                    raise

                logger.warning(
                    "smart_router_fallback_to_frontier",
                    local_error=str(e),
                    prompt_preview=prompt[:60],
                )
                fallback_resp = await self.frontier_client.generate(
                    prompt,
                    system_prompt=system_prompt,
                    chat_history=history,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    context=context,
                )
                fallback_resp.metadata.update(
                    {
                        "routed_to": "frontier",
                        "routing_strategy": decision.strategy.value,
                        "complexity_score": decision.complexity_score,
                        "routing_reason": f"fallback_local_error: {e!s}",
                        "fallback_triggered": True,
                        "total_latency_ms": (time.perf_counter() - start) * 1000,
                    }
                )
                return fallback_resp

        # Target: Frontier (Gemini)
        response = await self.frontier_client.generate(
            prompt,
            system_prompt=system_prompt,
            chat_history=history,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            context=context,
        )
        response.metadata.update(
            {
                "routed_to": "frontier",
                "routing_strategy": decision.strategy.value,
                "complexity_score": decision.complexity_score,
                "routing_reason": decision.reason,
                "fallback_triggered": decision.metadata.get("fallback_triggered", False),
            }
        )
        return response

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        strategy_override: str | None = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens dynamically from Local LLM or Frontier Gemini."""
        history = chat_history or (context.get("chat_history") if context else None)
        if hasattr(self.router, "decide"):
            decision = await self.router.decide(prompt, strategy_override=strategy_override, context=context)
        else:
            decision = self.router.classify(prompt, strategy_override=strategy_override, context=context)

        chosen_model = (
            getattr(self.local_client, "model_name", "Qwen/Qwen2.5-7B-Instruct")
            if decision.target == "local"
            else getattr(self.frontier_client, "model_name", "gemini-2.5-flash")
        )
        if context is not None:
            context["routed_to"] = decision.target
            context["model"] = chosen_model
            context["routing_reason"] = decision.reason
            context["fallback_triggered"] = decision.metadata.get("fallback_triggered", False)

        logger.info(
            "smart_router_stream_decision",
            target=decision.target,
            strategy=decision.strategy.value,
            complexity_score=decision.complexity_score,
            reason=decision.reason,
        )

        if decision.target == "local":
            try:
                async for token in self.local_client.stream(
                    prompt,
                    system_prompt=system_prompt,
                    chat_history=history,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    context=context,
                ):
                    yield token
                return
            except Exception as e:
                self.router.record_local_failure(e)
                if not self.router.fallback_enabled:
                    raise

                logger.warning(
                    "smart_router_stream_fallback_to_frontier",
                    local_error=str(e),
                    prompt_preview=prompt[:60],
                )
                if context is not None:
                    context["fallback_triggered"] = True
                    context["routed_to"] = "frontier"
                    context["model"] = getattr(self.frontier_client, "model_name", "gemini-2.5-flash")

                async for token in self.frontier_client.stream(
                    prompt,
                    system_prompt=system_prompt,
                    chat_history=history,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    context=context,
                ):
                    yield token
                return

        # Target: Frontier (Gemini)
        async for token in self.frontier_client.stream(
            prompt,
            system_prompt=system_prompt,
            chat_history=history,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            context=context,
        ):
            yield token

    def health(self) -> dict[str, Any]:
        """Aggregate health status of Frontier, Local, and Router."""
        return {
            "provider": self.provider_name,
            "status": "healthy",
            "router": self.router.status(),
            "frontier": self.frontier_client.health(),
            "local": self.local_client.health(),
        }
