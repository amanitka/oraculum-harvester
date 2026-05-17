from abc import ABC, abstractmethod
from typing import Generic, NamedTuple, TypeVar

from pydantic import BaseModel

from analyst.application.agents.context import AgentContext

TOutput = TypeVar("TOutput", bound=BaseModel)


class AgentOutput(NamedTuple):
    """Wrapper for an agent's structured output and its token usage."""

    result: TOutput
    tokens: int


class Agent(ABC, Generic[TOutput]):
    """
    Base class for all analysis agents in the workflow.
    """

    name: str
    system_prompt: str
    output_model: type[TOutput]

    def __init__(self) -> None:
        pass

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentOutput[TOutput]:
        """
        Executes the agent's logic using the provided context.

        Args:
            ctx: The context for the current analysis run, providing access
                 to shared state, read-only data tools, and the LLM client.

        Returns:
            An AgentOutput containing the structured result and the total tokens consumed.
        """
        pass
