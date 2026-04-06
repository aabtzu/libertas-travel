from fiat_lux_agents import LLMBase, SummaryBot

# Model constants — use these everywhere, never hardcode model strings
SONNET = "claude-sonnet-4-6"  # quality tasks: parsing, chat, reasoning
HAIKU = "claude-haiku-4-5-20251001"  # speed/cost tasks: classification, filtering


def make_llm(model=SONNET, max_tokens=2048) -> LLMBase:
    return LLMBase(model=model, max_tokens=max_tokens)


def make_summary_bot(description: str) -> SummaryBot:
    return SummaryBot(dataset_description=description, model=SONNET)
