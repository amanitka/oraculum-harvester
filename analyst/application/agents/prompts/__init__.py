from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent

# File names of available prompts
PLANNER_PROMPT = "planner.md"
FUNDAMENTALS_PROMPT = "fundamentals.md"
SHARE_PRICE_PROMPT = "share_price.md"
VALUATION_PROMPT = "valuation.md"
SYNTHESIZER_PROMPT = "synthesizer.md"
NEWS_PROMPT = "news.md"
RISK_PROMPT = "risk.md"
CRITIC_PROMPT = "critic.md"
CASH_FLOW_PROMPT = "cash_flow.md"
FACTSHEET_PROMPT = "factsheet.md"


def load_prompt(file_name: str) -> str:
    """Load a prompt from the specified file."""
    prompt_path = _PROMPT_DIR / file_name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text()