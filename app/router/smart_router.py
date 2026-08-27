from __future__ import annotations

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


class ComplexityScorer:
    """Evaluates prompt linguistic features, reasoning depth, and context length to score complexity."""

    # Keywords indicating high complexity, deep reasoning, or system architecture
    HIGH_COMPLEXITY_PATTERNS: ClassVar[list[str]] = [
        r"\banalyze\b",
        r"\barchitect\b",
        r"\bsynthesize\b",
        r"\bcompare and contrast\b",
        r"\bevaluate trade-?offs\b",
        r"\bmulti-?step\b",
        r"\bsystem design\b",
        r"\bdistributed\b",
        r"\brace condition\b",
        r"\bmathematical proof\b",
        r"\bsecurity audit\b",
        r"\brefactor architecture\b",
        r"\boptimize algorithm\b",
        r"\bformal verification\b",
        r"\broot cause analysis\b",
        r"\bdeep dive\b",
    ]

    # Keywords indicating routine, straightforward, or low-complexity tasks
    LOW_COMPLEXITY_PATTERNS: ClassVar[list[str]] = [
        r"\bsummarize in (?:one|1|two|2) sentences?\b",
        r"\btranslate (?:to|into)\b",
        r"\bfix (?:the )?grammar\b",
        r"\bhello\b",
        r"\bhi\b",
        r"\bhey\b",
        r"\bwhat is the capital of\b",
        r"\bextract (?:the )?(?:email|phone|name|address|date)\b",
        r"\brephrase\b",
        r"\bspell check\b",
        r"\bformat as (?:json|csv|markdown)\b",
        r"\bconvert to uppercase\b",
    ]

    def __init__(self, threshold: float = 0.55) -> None:
        self.threshold = threshold
        self._high_regex = [re.compile(p, re.IGNORECASE) for p in self.HIGH_COMPLEXITY_PATTERNS]
        self._low_regex = [re.compile(p, re.IGNORECASE) for p in self.LOW_COMPLEXITY_PATTERNS]

    def score(self, prompt: str) -> float:
        """Calculate a normalized complexity score between 0.0 (very simple) and 1.0 (highly complex)."""
        if not prompt or not prompt.strip():
            return 0.1

        text = prompt.strip()
        word_count = len(text.split())

        # Baseline score around 0.35
        score = 0.35

        # 1. Length adjustments
        if word_count > 400:
            score += 0.30
        elif word_count > 150:
            score += 0.20
        elif word_count > 60:
            score += 0.10
        elif word_count < 10:
            score -= 0.15

        # 2. High complexity pattern matches (+0.12 per match, up to +0.40)
        high_matches = sum(1 for r in self._high_regex if r.search(text))
        score += min(high_matches * 0.12, 0.40)

        # 3. Low complexity pattern matches (-0.20 per match)
        low_matches = sum(1 for r in self._low_regex if r.search(text))
        score -= low_matches * 0.20

        # 4. Code block detection (+0.15 if user pasted code snippets)
        if "```" in text or "def " in text or "function " in text or "class " in text:
            score += 0.15

        # Clamp between 0.05 and 0.99
        return round(max(0.05, min(0.99, score)), 3)


class SmartAIRouter:
    """Production AI Router that dynamically routes prompts between Local LLM and Frontier Models."""

    def __init__(
        self,
        default_strategy: RoutingStrategy = RoutingStrategy.AUTO,
        complexity_threshold: float = 0.55,
        fallback_enabled: bool = True,
    ) -> None:
        self.default_strategy = default_strategy
        self.complexity_threshold = complexity_threshold
        self.fallback_enabled = fallback_enabled
        self.scorer = ComplexityScorer(threshold=complexity_threshold)

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

    def classify(
        self,
        prompt: str,
        *,
        strategy_override: str | RoutingStrategy | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Determine routing target and rationale for the given prompt."""
        # Check strategy precedence
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

        # 1. Strategy: LOCAL_ONLY
        if active_strategy == RoutingStrategy.LOCAL_ONLY:
            return RoutingDecision(
                target="local",
                strategy=active_strategy,
                complexity_score=self.scorer.score(prompt),
                reason="explicit_local_only_strategy",
            )

        # 2. Strategy: FRONTIER_ONLY
        if active_strategy == RoutingStrategy.FRONTIER_ONLY:
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=self.scorer.score(prompt),
                reason="explicit_frontier_only_strategy",
            )

        complexity = self.scorer.score(prompt)

        # 3. Check Circuit Breaker (if Local is failing, fallback to Frontier)
        if not self.is_local_available and self.fallback_enabled:
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=complexity,
                reason="circuit_breaker_local_temporarily_disabled",
                metadata={"consecutive_failures": self._consecutive_local_failures},
            )

        # 4. Strategy: LOCAL_FIRST (attempts local unless prompt is extreme complexity > 0.85)
        if active_strategy == RoutingStrategy.LOCAL_FIRST:
            if complexity > 0.85:
                return RoutingDecision(
                    target="frontier",
                    strategy=active_strategy,
                    complexity_score=complexity,
                    reason="local_first_extreme_complexity_escalation",
                )
            return RoutingDecision(
                target="local",
                strategy=active_strategy,
                complexity_score=complexity,
                reason="local_first_preference",
            )

        # 5. Strategy: FRONTIER_FIRST (defaults to frontier unless prompt is trivial < 0.25)
        if active_strategy == RoutingStrategy.FRONTIER_FIRST:
            if complexity < 0.25:
                return RoutingDecision(
                    target="local",
                    strategy=active_strategy,
                    complexity_score=complexity,
                    reason="frontier_first_trivial_prompt_delegation",
                )
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=complexity,
                reason="frontier_first_preference",
            )

        # 6. Strategy: AUTO (Threshold based)
        if complexity >= self.complexity_threshold:
            return RoutingDecision(
                target="frontier",
                strategy=active_strategy,
                complexity_score=complexity,
                reason=f"complexity_score_{complexity}_exceeds_threshold_{self.complexity_threshold}",
            )

        return RoutingDecision(
            target="local",
            strategy=active_strategy,
            complexity_score=complexity,
            reason=f"complexity_score_{complexity}_below_threshold_{self.complexity_threshold}",
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
