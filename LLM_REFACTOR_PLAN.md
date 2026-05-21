# LLM Redesign & Multi-Provider Failover Strategy

This document outlines the plan to refactor the application's LLM integration to support a cost-optimized,
multi-provider routing and failover system.

## 1. Objective

Redesign the LLM execution layer to:

1. Utilize abstract model aliases (e.g., `flash-tier`, `pro-tier`) instead of hardcoded model names.
2. Prioritize cost-effective models (e.g., Gemini) to maximize free credits.
3. Seamlessly fail over to a secondary provider (e.g., Groq, OpenAI) in case of API errors, rate limits, or quota
   issues.
4. Manage all provider configurations centrally in `config.yaml`.
5. Enable flexible, per-agent model selection for optimal cost and performance.

## 2. Core Architectural Changes

We will introduce `LiteLLM` as a routing layer between the application and the various LLM providers. This library is
purpose-built for this scenario.

### 2.1. Model Tiers (Aliases)

Instead of agents calling a specific model like `"gemini-2.5-flash-lite"`, they will request a logical **tier**. This
decouples the agent's logic from the specific model implementation.

We will define three initial tiers:

- `flash-tier`: For simple, high-volume tasks. (Lowest cost)
- `pro-tier`: For complex analysis and synthesis. (Balanced cost/performance)
- `specialist-tier`: For tasks requiring the most powerful models available. (Highest cost)

### 2.2. Configuration-Driven Routing

The `config.yaml` file will be the single source of truth for defining which models belong to which tier and in what
priority order. `LiteLLM` will use this configuration to manage the routing.

## 3. Implementation Plan

### Step 3.1: Add `litellm` Dependency

First, add `litellm` to your project's dependencies, likely in `pyproject.toml`.

### Step 3.2: Redesign `config.yaml`

The current `llm` section in `config.yaml` will be replaced with a more structured list of model deployments using the
optimal models selected from your list.

**Proposed `config.yaml` structure:**

```yaml
llm:
  # A list of all available model deployments.
  # 'alias' groups them into tiers. 'order' defines failover priority within a tier.
  deployments:
    # --- Tier 1: Flash Models (for simple, high-volume tasks) ---
    - alias: "flash-tier"
      model: "gemini/gemini-3.1-flash-lite-preview"
      api_key: ${GEMINI_API_KEY}
      order: 1 # Primary: Newest, agentic, and extremely cheap.
    - alias: "flash-tier"
      model: "groq/llama-3.1-8b-instant-128k"
      api_key: ${GROQ_API_KEY}
      order: 2 # Fallback: Negligible cost and incredible speed.

    # --- Tier 2: Pro Models (for robust analysis) ---
    - alias: "pro-tier"
      model: "gemini/gemini-3.5-flash"
      api_key: ${GEMINI_API_KEY}
      order: 1 # Primary: Google's newest production model for agentic work.
    - alias: "pro-tier"
      model: "groq/llama-3.3-70b-versatile-128k"
      api_key: ${GROQ_API_KEY}
      order: 2 # Fallback: Powerful 70B model with great cost-performance.

    # --- Tier 3: Specialist Models (for critical synthesis) ---
    - alias: "specialist-tier"
      model: "gemini/gemini-3.1-pro"
      api_key: ${GEMINI_API_KEY}
      order: 1 # Primary: Flagship model for the most complex tasks.
    - alias: "specialist-tier"
      model: "groq/llama-3.3-70b-versatile-128k"
      api_key: ${GROQ_API_KEY}
      order: 2 # Fallback: Cross-provider failover to a powerful Groq model.

  # Global settings applied to all calls via the router
  router_settings:
    temperature: 0.0 # Enforce deterministic logic
    num_retries: 3
    routing_strategy: "simple-shuffle" # simple-shuffle respects the 'order' field
```

### Step 3.3: Update `common/config.py`

The `_LlmConfig` class will be updated to parse this new structure.

```python
# In common/config.py

from pydantic import BaseModel, Field
from typing import List, Optional


# ... other imports

class _LlmDeploymentConfig(BaseModel):
    alias: str
    model: str
    api_key: str
    order: int


class _LlmRouterSettingsConfig(BaseModel):
    temperature: float = 0.0
    num_retries: int = 3
    routing_strategy: str = "simple-shuffle"


class _LlmConfig:
    """Settings for the Large Language Model provider."""

    def __init__(self, source: EnvYAML) -> None:
        self.deployments: List[_LlmDeploymentConfig] = [
            _LlmDeploymentConfig(**d) for d in source.get("llm.deployments", [])
        ]
        self.router_settings: _LlmRouterSettingsConfig = _LlmRouterSettingsConfig(
            **source.get("llm.router_settings", {})
        )

# ... rest of the Config class remains the same
```

### Step 3.4: Implement the `LiteLLM` Router

Create a new module, `common/llm/router.py`, to initialize the `LiteLLM` router based on the loaded configuration. This
router will become our new `LlmClient`.

```python
# In a new file: common/llm/router.py

from litellm import Router
from common.config import config
from common.llm.base import LlmClient, LlmResponse  # Assuming you have these base classes


class LiteLLMRouterClient(LlmClient):
    """An LlmClient implementation powered by the LiteLLM router."""

    def __init__(self):
        model_list = [
            {
                "model_name": deployment.alias,
                "litellm_params": {
                    "model": deployment.model,
                    "api_key": deployment.api_key,
                },
                "order": deployment.order,
            }
            for deployment in config.llm.deployments
        ]

        self._router = Router(
            model_list=model_list,
            routing_strategy=config.llm.router_settings.routing_strategy,
            num_retries=config.llm.router_settings.num_retries,
            # This ensures that if a call to "flash-tier" fails, it retries on other "flash-tier" models
            fallbacks=[{d.alias: [d.alias]} for d in config.llm.deployments],
        )

    async def complete(
            self,
            messages: list[dict],
            model: str,  # This will now be the alias, e.g., "flash-tier"
            max_tokens: int,
            temperature: float | None = None,
            response_format: Any | None = None,  # Keep your existing signature
    ) -> LlmResponse:
        # Use global temperature from config, but allow per-call override
        final_temperature = temperature if temperature is not None else config.llm.router_settings.temperature

        response = await self._router.acompletion(
            model=model,  # The alias acts as the key
            messages=messages,
            max_tokens=max_tokens,
            temperature=final_temperature,
        )

        # Adapt the LiteLLM response to your internal LlmResponse object
        # This is an example, you'll need to map the fields correctly
        return LlmResponse(
            text=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

```

### Step 3.5: Update Agent Context

In `analyst/application/agents/context_factory.py` (or wherever you instantiate your `AgentContext`), you will now
provide the `LiteLLMRouterClient`.

```python
# In your context factory...
from common.llm.router import LiteLLMRouterClient

# ...
llm_client = LiteLLMRouterClient()
agent_context = AgentContext(
    # ... other parameters
    llm=llm_client,
    # ...
)
```

### Step 3.6: Refactor Agents to Use Tiers

Finally, update agents like `CashFlowAgent` to call the model alias instead of a hardcoded name.

**`analyst/application/agents/cash_flow.py` (After changes):**

```python
# ... imports

class CashFlowAgent(Agent[CashFlowOutput]):
    # ...

    async def run(self, ctx: AgentContext) -> AgentOutput[CashFlowOutput]:
        # ... (rest of the data preparation logic is unchanged)

        response = await ctx.llm.complete(
            messages=messages,
            model="flash-tier",  # <-- Use the abstract tier name
            max_tokens=config.llm.max_tokens,
            # Temperature can be omitted to use the deterministic default from config
            # temperature=0.2, 
            response_format=self.output_model,
        )

        # ... (rest of the logic is unchanged)
```

## 4. Per-Agent Configuration

Your question about per-agent vs. global configuration is excellent. The proposed design provides the best of both
worlds:

- **Centralized Configuration:** The `config.yaml` file remains the single source of truth for what "flash-tier" or "
  pro-tier" means at any given time. You can swap `gemini` for `claude` in the config without touching any agent code.
- **Decentralized Usage:** Each agent can independently decide which tier is appropriate for its task.
    - `CashFlowAgent` might use `flash-tier`.
    - `SynthesizerAgent` might require `pro-tier` for higher quality output.
    - A future `ImageAnalysisAgent` could use a `specialist-tier` configured with a multi-modal model.

This approach is highly flexible and aligns with modern, cost-conscious AI development.