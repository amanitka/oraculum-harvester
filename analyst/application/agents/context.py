from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel

from common.domain.income_statement import IncomeStatementTemplate, StatementVariant
from common.llm.base import LlmClient
from analyst.application.agents.tools import DataTools


@dataclass
class AgentContext:
    """
    State and dependencies provided to every agent during an analysis run.
    """

    ticker: str
    market: str
    as_of: date
    template: IncomeStatementTemplate
    default_variant: StatementVariant
    tools: DataTools
    llm: LlmClient
    token_budget: int
    prior_outputs: dict[str, BaseModel]
