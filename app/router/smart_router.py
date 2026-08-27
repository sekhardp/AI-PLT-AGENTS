from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger(__name__)


class RoutingStrategy(str, Enum):
    AUTO = "AUTO"
    LOCAL_FIRST = "LOCAL_FIRST"
    FRONTIER_FIRST = "FRONTIER_FIRST"
    LOCAL_ONLY = "LOCAL_ONLY"
    FRONTIER_ONLY = "FRONTIER_ONLY"


@dataclass
class RoutingDecision:
    """Decision produced by the Smart AI Router."""

    target: str  # "local" or "frontier"
    strategy: RoutingStrategy
    complexity_score: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)




ROUTER_DECISION_PROMPT = (
    "You are an intelligent AI router. Your job is to classify incoming user questions into one of two execution tiers:\n"
    '- "local": If the question is simple, routine, a general greeting, everyday task, fact lookup, or just a single tool-call question (e.g. check weather, simple database query).\n'
    '- "frontier": If the question is complex, requires deep reasoning, multi-step planning, mathematical proof, system architecture design, or detailed analysis.\n\n'
    'Respond ONLY with a valid JSON object in this format:\n'
    '{"target": "local", "reason": "simple query"} or {"target": "frontier", "reason": "complex reasoning"}\n'
    'Do NOT output markdown fences, code blocks, or any other text.'
)


class SmartAIRouter:
    """Production AI Router that dynamically routes prompts between Local LLM and Frontier Models."""

    def __init__(
        self,
        local_client: Any | None = None,
        default_strategy: RoutingStrategy = RoutingStrategy.AUTO,
        complexity_threshold: float = 0.55,
        fallback_enabled: bool = True,
    ) -> None:
        self.local_client = local_client
        self.default_strategy = default_strategy
        self.complexity_threshold = complexity_threshold
        self.fallback_enabled = fallback_enabled

        # Circuit breaker state
        self._consecutive_local_failures = 0
        self._circuit_open_until = 0.0
        self._failure_threshold = 3
        self._recovery_cooldown_seconds = 30.0

    @property
    def is_local_available(self) -> bool:
        """Check if circuit breaker allows routing to Local LLM."""
        if self._consecutive_local_failures >= self._failure_threshold:
            return time.time() >= self._circuit_open_until
        return True

    def record_local_success(self) -> None:
        """Reset circuit breaker on successful Local LLM execution."""
        if self._consecutive_local_failures > 0:
            logger.info("router_local_circuit_breaker_recovered")
        self._consecutive_local_failures = 0
        self._circuit_open_until = 0.0

    def record_local_failure(self, error: Exception) -> None:
        """Trip circuit breaker on consecutive Local LLM errors."""
        self._consecutive_local_failures += 1
        logger.warning(
            "router_local_failure_recorded",
            consecutive_failures=self._consecutive_local_failures,
            error=str(error),
        )
        if self._consecutive_local_failures >= self._failure_threshold:
            self._circuit_open_until = time.time() + self._recovery_cooldown_seconds
            logger.error(
                "router_local_circuit_tripped",
                cooldown_seconds=self._recovery_cooldown_seconds,
            )

    async def decide(
        self,
        prompt: str,
        *,
        strategy_override: str | RoutingStrategy | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Asynchronously determine routing decision using the Local LLM as an intelligent classifier.

        If the Local LLM is unreachable or fails, immediately falls back to Frontier.
        """
        active_strategy = self.default_strategy
        if strategy_override:
            try:
                active_strategy = RoutingStrategy(str(strategy_override).upper())
            except ValueError:
                logger.warning("invalid_strategy_override", strategy=strategy_override)

        if context and "routing_strategy" in context:
            try:
                active_strategy = RoutingStrategy(str(context["routing_strategy"]).upper())
            except ValueError:
                pass

        if active_strategy == RoutingStrategy.LOCAL_ONLY:
            return RoutingDecision(
                target="local",
                strategy=active_strategy,
                complexity_score=0.2,
                reason="explicit_local_only_strategy",
            )
        if active_strategy == RoutingStrategy.FRONTIER_ONLY:
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=0.8,
                reason="explicit_frontier_only_strategy",
            )

        if not self.is_local_available and self.fallback_enabled:
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=0.9,
                reason="circuit_breaker_local_offline_fallback",
                metadata={"consecutive_failures": self._consecutive_local_failures},
            )

        if not self.local_client:
            return self.classify(
                prompt,
                strategy_override=strategy_override,
                context=context,
            )

        try:
            resp = await self.local_client.generate(
                prompt=prompt,
                system_prompt=ROUTER_DECISION_PROMPT,
                max_tokens=60,
                temperature=0.1,
            )
            cleaned = resp.content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            data = json.loads(cleaned)
            target = str(data.get("target", "local")).lower().strip()
            if target not in ("local", "frontier"):
                target = "local"
            reason = data.get("reason", f"llm_classified_{target}")

            self.record_local_success()
            return RoutingDecision(
                target=target,
                strategy=active_strategy,
                complexity_score=0.15 if target == "local" else 0.85,
                reason=reason,
                metadata={"classified_by": "local_llm"},
            )
        except Exception as e:
            self.record_local_failure(e)
            logger.warning(
                "smart_router_decision_failed_falling_back_to_frontier",
                error=str(e),
            )
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=0.85,
                reason=f"local_unreachable_fallback: {e!s}",
                metadata={"fallback_triggered": True},
            )

    def classify(
        self,
        prompt: str,
        *,
        strategy_override: str | RoutingStrategy | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Lightweight synchronous fallback for offline or quick check."""
        active_strategy = self.default_strategy
        if strategy_override:
            try:
                active_strategy = RoutingStrategy(str(strategy_override).upper())
            except ValueError:
                pass

        if context and "routing_strategy" in context:
            try:
                active_strategy = RoutingStrategy(str(context["routing_strategy"]).upper())
            except ValueError:
                pass

        if active_strategy == RoutingStrategy.LOCAL_ONLY:
            return RoutingDecision(target="local", strategy=active_strategy, complexity_score=0.15, reason="explicit_local_only")
        if active_strategy == RoutingStrategy.FRONTIER_ONLY or (not self.is_local_available and self.fallback_enabled):
            return RoutingDecision(target="frontier", strategy=active_strategy, complexity_score=0.85, reason="circuit_breaker_or_frontier_only")

        # Fast heuristic fallback: complex keywords go to frontier, simple go to local
        is_complex = any(w in prompt.lower() for w in ("analyze", "architect", "distributed", "consensus", "paxos", "proof", "verification"))
        target = "frontier" if is_complex else "local"
        return RoutingDecision(
            target=target,
            strategy=active_strategy,
            complexity_score=0.85 if is_complex else 0.15,
            reason=f"heuristic_{target}",
        )

    def status(self) -> dict[str, Any]:
        """Return operational state and telemetry of the router."""
        return {
            "default_strategy": self.default_strategy.value,
            "complexity_threshold": self.complexity_threshold,
            "fallback_enabled": self.fallback_enabled,
            "circuit_breaker": {
                "local_available": self.is_local_available,
                "consecutive_failures": self._consecutive_local_failures,
                "cooldown_active": time.time() < self._circuit_open_until,
            },
        }
