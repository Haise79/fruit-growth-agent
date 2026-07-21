from typing import Protocol

from fruit_agent.model_gateway.schemas import CopilotProviderResponse, ProviderResponse


class ModelProvider(Protocol):
    async def complete(
        self,
        prompt: dict[str, object],
        timeout_seconds: float,
    ) -> ProviderResponse | CopilotProviderResponse: ...
