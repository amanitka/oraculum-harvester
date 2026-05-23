"""
Agent responsible for summarizing news and sentiment for a given ticker.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from analyst.application.agents.prompts import (
    load_prompt,
    NEWS_SUMMARY_PROMPT,
)

if TYPE_CHECKING:
    from analyst.application.agents.tools import DataTools
    from common.llm.client import LlmClient

logger = logging.getLogger(__name__)


class NewsAgent:
    """
    An agent that analyzes recent news articles to generate a summary of key events
    and prevailing sentiment.
    """

    def __init__(self, llm_client: LlmClient, tools: DataTools):
        self._llm_client = llm_client
        self._tools = tools

    async def analyze_news(self, ticker: str) -> str:
        """
        Fetches recent news, invokes an LLM to summarize it, and returns the result.

        Args:
            ticker: The ticker symbol to analyze.

        Returns:
            A Markdown-formatted string summarizing the news and sentiment.
        """
        logger.info("NewsAgent starting analysis for ticker: %s", ticker)

        # Fetch recent news using the data tools
        news_markdown = await self._tools.get_recent_news(ticker=ticker, days_back=30)

        if "No recent news found" in news_markdown:
            logger.warning("No recent news found for ticker: %s", ticker)
            return "No significant recent news found for this ticker."

        # Prepare and execute the LLM call
        prompt = load_prompt(NEWS_SUMMARY_PROMPT)
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Here is the recent news for {ticker}:\n\n{news_markdown}",
            },
        ]

        response = await self._llm_client.get_completion(messages)

        logger.info("NewsAgent successfully generated summary for ticker: %s", ticker)
        return response
