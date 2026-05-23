"""
Agent responsible for summarizing news and sentiment for a given ticker.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from analyst.application.agents.base import Agent, AgentContext, AgentOutput
from analyst.application.agents.prompts import (
    load_prompt,
    NEWS_SUMMARY_PROMPT,
)

if TYPE_CHECKING:
    from common.llm.client import LlmClient

logger = logging.getLogger(__name__)


class NewsOutput(AgentOutput):
    summary: str


class NewsAgent(Agent[NewsOutput]):
    """
    An agent that analyzes recent news articles to generate a summary of key events
    and prevailing sentiment.
    """
    name = "News"
    output_model = NewsOutput

    def __init__(self) -> None:
        self.system_prompt = load_prompt(NEWS_SUMMARY_PROMPT)

    async def run(self, ctx: AgentContext) -> AgentOutput[NewsOutput]:
        """
        Fetches recent news, invokes an LLM to summarize it, and returns the result.
        """
        logger.info("NewsAgent starting analysis for ticker: %s", ctx.ticker)

        # Fetch recent news using the data tools
        news_markdown = await ctx.tools.get_recent_news(ticker=ctx.ticker, days_back=30)

        if "No recent news found" in news_markdown:
            logger.warning("No recent news found for ticker: %s", ctx.ticker)
            return self.create_output(summary="No significant recent news found for this ticker.")

        # Prepare and execute the LLM call
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Here is the recent news for {ctx.ticker}:\n\n{news_markdown}",
            },
        ]

        response = await ctx.llm.get_completion(messages)

        logger.info("NewsAgent successfully generated summary for ticker: %s", ctx.ticker)
        return self.create_output(summary=response)
