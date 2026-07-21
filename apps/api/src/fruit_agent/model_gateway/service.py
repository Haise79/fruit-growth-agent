import asyncio
from dataclasses import dataclass
from time import perf_counter
from collections.abc import Sequence
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.knowledge.models import MerchantKnowledge
from fruit_agent.model_gateway.ports import ModelProvider
from fruit_agent.model_gateway.redaction import redact_prompt
from fruit_agent.model_gateway.schemas import (
    CopilotGatewayOutput,
    CopilotProviderResponse,
    GatewaySuggestion,
    ModelProfile,
    ProviderResponse,
)

logger = structlog.get_logger(__name__)
MODEL_TIMEOUT_SECONDS = 8.0
MAX_PRIMARY_ATTEMPTS = 3
COPILOT_TOTAL_TIMEOUT_SECONDS = 14.0


class NoQualifiedModelError(RuntimeError):
    pass


class ProviderUnavailableError(RuntimeError):
    pass


class InvalidModelOutputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    profile: ModelProfile
    provider: ModelProvider


def select_model(candidates: Sequence[ModelProfile]) -> ModelProfile:
    qualified = [
        model
        for model in candidates
        if model.fact_error_rate < 0.02 and model.high_risk_recall >= 0.95
    ]
    if not qualified:
        raise NoQualifiedModelError("no model satisfies quality thresholds")
    return min(
        qualified,
        key=lambda model: model.estimated_cost_per_1k_tokens,
    )


class ModelGateway:
    def __init__(
        self,
        *,
        session: AsyncSession,
        providers: Sequence[ProviderBinding],
    ) -> None:
        self.session = session
        self.providers = list(providers)

    def _qualified_bindings(self) -> list[ProviderBinding]:
        qualified = [
            binding
            for binding in self.providers
            if binding.profile.fact_error_rate < 0.02
            and binding.profile.high_risk_recall >= 0.95
        ]
        if not qualified:
            raise NoQualifiedModelError("no model satisfies quality thresholds")
        return sorted(
            qualified,
            key=lambda binding: (
                binding.profile.estimated_cost_per_1k_tokens
            ),
        )

    async def _complete(
        self,
        binding: ProviderBinding,
        prompt: dict[str, object],
        attempts: int,
    ) -> tuple[ProviderResponse, int, float]:
        started = perf_counter()
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                async with asyncio.timeout(MODEL_TIMEOUT_SECONDS):
                    response = await binding.provider.complete(
                        prompt,
                        MODEL_TIMEOUT_SECONDS,
                    )
                if not isinstance(response, ProviderResponse):
                    raise InvalidModelOutputError(
                        "provider returned non-suggestion output"
                    )
                return response, attempt - 1, perf_counter() - started
            except (TimeoutError, ProviderUnavailableError) as exc:
                last_error = exc
                await logger.awarning(
                    "model_provider_attempt_failed",
                    model_name=binding.profile.name,
                    attempt=attempt,
                    timeout_seconds=MODEL_TIMEOUT_SECONDS,
                    error_type=type(exc).__name__,
                )
        raise ProviderUnavailableError(
            f"provider {binding.profile.name} unavailable"
        ) from last_error

    async def _complete_copilot(
        self,
        binding: ProviderBinding,
        prompt: dict[str, object],
        attempts: int,
    ) -> tuple[CopilotProviderResponse, int, float]:
        started = perf_counter()
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                async with asyncio.timeout(MODEL_TIMEOUT_SECONDS):
                    response = await binding.provider.complete(
                        prompt,
                        MODEL_TIMEOUT_SECONDS,
                    )
                if not isinstance(response, CopilotProviderResponse):
                    raise InvalidModelOutputError(
                        "provider returned malformed copilot output"
                    )
                return response, attempt - 1, perf_counter() - started
            except InvalidModelOutputError:
                raise
            except Exception as exc:
                last_error = exc
                await logger.awarning(
                    "copilot_provider_attempt_failed",
                    model_name=binding.profile.name,
                    attempt=attempt,
                    timeout_seconds=MODEL_TIMEOUT_SECONDS,
                    error_type=type(exc).__name__,
                )
        raise ProviderUnavailableError(
            f"provider {binding.profile.name} unavailable"
        ) from last_error

    async def _validate_references(
        self,
        tenant_id: UUID,
        referenced_ids: list[UUID],
    ) -> None:
        if not referenced_ids:
            return
        known_ids = set(
            await self.session.scalars(
                select(MerchantKnowledge.id).where(
                    MerchantKnowledge.tenant_id == tenant_id,
                    MerchantKnowledge.id.in_(referenced_ids),
                )
            )
        )
        if known_ids != set(referenced_ids):
            raise InvalidModelOutputError(
                "model referenced unknown tenant knowledge"
            )

    async def suggest(
        self,
        *,
        tenant_id: UUID,
        prompt: dict[str, object],
    ) -> GatewaySuggestion:
        redacted_prompt = redact_prompt(prompt)
        bindings = self._qualified_bindings()
        primary = bindings[0]
        degraded = False
        total_retries = 0

        try:
            response, retries, latency = await self._complete(
                primary,
                redacted_prompt,
                MAX_PRIMARY_ATTEMPTS,
            )
            selected = primary
            total_retries = retries
        except ProviderUnavailableError:
            if len(bindings) < 2:
                raise
            selected = bindings[1]
            degraded = True
            response, retries, latency = await self._complete(
                selected,
                redacted_prompt,
                1,
            )
            total_retries = (MAX_PRIMARY_ATTEMPTS - 1) + retries

        await self._validate_references(
            tenant_id,
            response.suggestion.referenced_knowledge_ids,
        )
        total_tokens = response.input_tokens + response.output_tokens
        cost = (
            total_tokens
            / 1000
            * selected.profile.estimated_cost_per_1k_tokens
        )
        await logger.ainfo(
            "model_call_completed",
            tenant_id=str(tenant_id),
            model_name=selected.profile.name,
            latency_seconds=latency,
            estimated_cost=cost,
            retry_count=total_retries,
            degraded=degraded,
        )
        return GatewaySuggestion(
            **response.suggestion.model_dump(),
            model_name=selected.profile.name,
            degraded=degraded,
            retry_count=total_retries,
            estimated_cost=cost,
        )

    async def suggest_copilot(
        self,
        *,
        tenant_id: UUID,
        prompt: dict[str, object],
    ) -> CopilotGatewayOutput:
        try:
            async with asyncio.timeout(COPILOT_TOTAL_TIMEOUT_SECONDS):
                return await self._suggest_copilot_within_deadline(
                    tenant_id=tenant_id,
                    prompt=prompt,
                )
        except TimeoutError as exc:
            raise ProviderUnavailableError(
                "copilot provider deadline exceeded"
            ) from exc

    async def _suggest_copilot_within_deadline(
        self,
        *,
        tenant_id: UUID,
        prompt: dict[str, object],
    ) -> CopilotGatewayOutput:
        redacted_prompt = redact_prompt(prompt)
        bindings = self._qualified_bindings()
        primary = bindings[0]
        degraded = False
        total_retries = 0

        try:
            response, retries, latency = await self._complete_copilot(
                primary,
                redacted_prompt,
                MAX_PRIMARY_ATTEMPTS,
            )
            selected = primary
            total_retries = retries
        except ProviderUnavailableError:
            if len(bindings) < 2:
                raise
            selected = bindings[1]
            degraded = True
            response, retries, latency = await self._complete_copilot(
                selected,
                redacted_prompt,
                1,
            )
            total_retries = (MAX_PRIMARY_ATTEMPTS - 1) + retries

        referenced_ids = [
            knowledge_id
            for suggestion in response.output.suggestions
            for knowledge_id in suggestion.referenced_knowledge_ids
        ]
        await self._validate_references(tenant_id, referenced_ids)
        total_tokens = response.input_tokens + response.output_tokens
        cost = (
            total_tokens
            / 1000
            * selected.profile.estimated_cost_per_1k_tokens
        )
        await logger.ainfo(
            "copilot_model_call_completed",
            tenant_id=str(tenant_id),
            model_name=selected.profile.name,
            latency_seconds=latency,
            estimated_cost=cost,
            retry_count=total_retries,
            degraded=degraded,
        )
        return CopilotGatewayOutput(
            **response.output.model_dump(),
            model_name=selected.profile.name,
            degraded=degraded,
            retry_count=total_retries,
            estimated_cost=cost,
        )
