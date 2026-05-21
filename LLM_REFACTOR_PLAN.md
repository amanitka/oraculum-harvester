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

We will use the official `openai` Python SDK (which is compatible with many providers like Groq, Together, and local models) to route requests between the application and the various LLM providers, and use a custom failover logic loop based on configuration tiers.

### 2.1. Model Tiers (Aliases)

Instead of agents calling a specific model like `"gemini-2.5-flash-lite"`, they will request a logical **tier**. This
decouples the agent's logic from the specific model implementation.

We will define three initial tiers:

- `flash-tier`: For simple, high-volume tasks. (Lowest cost)
- `pro-tier`: For complex analysis and synthesis. (Balanced cost/performance)
- `specialist-tier`: For tasks requiring the most powerful models available. (Highest cost)

### 2.2. Configuration-Driven Routing

The `config.yaml` file will be the single source of truth for defining which models belong to which tier and in what
priority order. Our custom router will use this configuration to manage the routing.

## 3. Implementation Plan

### Step 3.1: Redesign `config.yaml`

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
      api_base: "https://generativelanguage.googleapis.com/v1beta/"
      order: 1 # Primary: Newest, agentic, and extremely cheap.
    - alias: "flash-tier"
      model: "llama-3.1-8b-instant"
      api_key: ${GROQ_API_KEY}
      api_base: "https://api.groq.com/openai/v1"
      order: 2 # Fallback: Negligible cost and incredible speed.

    # --- Tier 2: Pro Models (for robust analysis) ---
    - alias: "pro-tier"
      model: "gemini/gemini-3.5-flash"
      api_key: ${GEMINI_API_KEY}
      api_base: "https://generativelanguage.googleapis.com/v1beta/"
      order: 1 # Primary: Google's newest production model for agentic work.
    - alias: "pro-tier"
      model: "llama-3.3-70b-versatile"
      api_key: ${GROQ_API_KEY}
      api_base: "https://api.groq.com/openai/v1"
      order: 2 # Fallback: Powerful 70B model with great cost-performance.

    # --- Tier 3: Specialist Models (for critical synthesis) ---
    - alias: "specialist-tier"
      model: "gemini/gemini-3.1-pro"
      api_key: ${GEMINI_API_KEY}
      api_base: "https://generativelanguage.googleapis.com/v1beta/"
      order: 1 # Primary: Flagship model for the most complex tasks.
    - alias: "specialist-tier"
      model: "llama-3.3-70b-versatile"
      api_key: ${GROQ_API_KEY}
      api_base: "https://api.groq.com/openai/v1"
      order: 2 # Fallback: Cross-provider failover to a powerful Groq model.

  # Global settings applied to all calls via the router
  router_settings:
    temperature: 0.0 # Enforce deterministic logic
    num_retries: 3
    routing_strategy: "priority" # Attempts models based on their 'order' value within the tier
```

### Step 3.2: Update `common/config.py`

The `_LlmConfig` class will be updated to parse this new structure.

```python
# In common/config.py

from pydantic import BaseModel
from typing import List


# ... other imports

class _LlmDeploymentConfig(BaseModel):
    alias: str
    model: str
    api_key: str
    api_base: str
    order: int


class _LlmRouterSettingsConfig(BaseModel):
    temperature: float = 0.0
    num_retries: int = 3
    routing_strategy: str = "priority"


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

### Step 3.3: Implement the Tier Router in `OpenAiClient`

Update `common/llm/openai_client.py` to route based on the requested model alias instead of the exact model name. The router must implement a `try-catch` and iterate through all deployments available for a given alias based on the `order` parameter until one succeeds.

```python
# In common/llm/openai_client.py

from openai import AsyncOpenAI
# ...

class OpenAiClient(LlmClient):
    """
    An adapter for the official OpenAI SDK that implements the LlmClient interface and tier-based routing.
    """
    
    # ...

    async def complete(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str, # This will now be the alias, e.g., "flash-tier"
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | dict[str, Any] | None = None,
    ) -> LlmResponse:
        
        # 1. Fetch deployments for the requested model alias, sorted by order
        deployments = sorted(
            [d for d in config.llm.deployments if d.alias == model],
            key=lambda d: d.order
        )
        
        if not deployments:
            raise ValueError(f"No deployments found for alias '{model}'")
            
        # 2. Loop through deployments and try to complete the request
        last_exception = None
        for deployment in deployments:
            client = AsyncOpenAI(api_key=deployment.api_key, base_url=deployment.api_base)
            
            # Implementation using the retry logic from the previous code,
            # but scoped to this specific deployment.
            try:
                # Add existing logic here, replacing self._client with the local client
                # and using deployment.model instead of model.
                pass 
            except Exception as e:
                logger.warning(f"Deployment {deployment.model} for tier {model} failed. Trying next.")
                last_exception = e
                continue
                
        raise RuntimeError(f"All deployments for tier {model} failed.") from last_exception

```

### Step 3.4: Update Agent Context

In `analyst/application/agents/context_factory.py` (or wherever you instantiate your `AgentContext`), no changes are required since it is already providing the `OpenAiClient`.

### Step 3.5: Refactor Agents to Use Tiers

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

The proposed design provides the best of both worlds:

- **Centralized Configuration:** The `config.yaml` file remains the single source of truth for what "flash-tier" or "pro-tier" means at any given time. You can swap models in the config without touching any agent code.
- **Decentralized Usage:** Each agent can independently decide which tier is appropriate for its task.
    - `CashFlowAgent` might use `flash-tier`.
    - `SynthesizerAgent` might require `pro-tier` for higher quality output.
    - A future `ImageAnalysisAgent` could use a `specialist-tier` configured with a multi-modal model.

This approach is highly flexible and aligns with modern, cost-conscious AI development.