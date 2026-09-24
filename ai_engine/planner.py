"""The diet planner: AI first when enabled, validated, with an automatic rule-based fallback.

    PlanRequest ─► compute_targets() ─► AI provider ─► validate ─► AI plan
                                            │ error          │ rejected
                                            └──────► rule-based engine ─► plan (+ reason)

Every plan records which engine produced it (``source``) and, if the AI was skipped, why
(``fallback_reason``) — so the fallback is visible to users, logs and metrics.
"""

import logging
import time

from ai_engine.diet_engine import GeneratedPlan, RuleBasedDietEngine, assemble_plan
from ai_engine.llm_providers import AIProviderError, LLMProvider
from ai_engine.nutrition import NutritionTargets, PlanRequest, compute_targets
from ai_engine.prompts import MEAL_PLAN_JSON_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from ai_engine.validation import AIValidationError, validate_ai_plan

logger = logging.getLogger("diet_planner.ai")


class DietPlanner:
    def __init__(
        self,
        provider: LLMProvider | None,
        *,
        ai_requested: bool,
        rule_engine: RuleBasedDietEngine | None = None,
    ) -> None:
        """``ai_requested`` reflects configuration (AI_PROVIDER is not ``rule_based``);
        ``provider`` is None when AI was requested but could not be set up."""
        self.provider = provider
        self.ai_requested = ai_requested
        self.rule_engine = rule_engine or RuleBasedDietEngine()

    @property
    def ai_available(self) -> bool:
        return self.ai_requested and self.provider is not None

    def generate(self, request: PlanRequest, *, use_ai: bool = True) -> GeneratedPlan:
        targets = compute_targets(request)
        if not self.ai_requested:
            return self.rule_engine.generate(request, targets)  # rules are the chosen engine

        if not use_ai:
            reason = "ai_disabled"
        elif self.provider is None:
            reason = "ai_not_configured"
        else:
            try:
                return self._generate_with_ai(request, targets)
            except (AIProviderError, AIValidationError) as exc:
                reason = exc.reason
                logger.warning("AI plan unavailable (%s); falling back to rules", exc)

        plan = self.rule_engine.generate(request, targets)
        return plan.model_copy(update={"fallback_reason": reason})

    def _generate_with_ai(self, request: PlanRequest, targets: NutritionTargets) -> GeneratedPlan:
        started = time.perf_counter()
        raw = self.provider.generate_json(
            SYSTEM_PROMPT, build_user_prompt(request, targets), MEAL_PLAN_JSON_SCHEMA
        )
        meals, ai_tips = validate_ai_plan(raw, request, targets)
        logger.info("AI plan accepted", extra={
            "ai_provider": self.provider.name,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        })
        return assemble_plan(
            request,
            targets,
            meals,
            source="ai",
            ai_provider=self.provider.name,
            ai_model=self.provider.model,
            extra_tips=ai_tips,
        )
