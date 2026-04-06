# How Libertas Uses fiat-lux-agents

[fiat-lux-agents](https://github.com/aabtzu/fiat-lux-agents) is the AI library that powers all Claude interactions in Libertas. It provides a thin, consistent wrapper around the Anthropic API so that individual features don't reinvent prompt handling, error management, or model selection.

---

## What Libertas Uses

Libertas uses two things from fiat-lux-agents directly:

| Class | Where used | Purpose |
|---|---|---|
| `LLMBase` | `agents/common/llm.py` | Base class for direct Claude API calls across all features |
| `SummaryBot` | `agents/common/llm.py` | Natural language Q&A over a dataset description |

Everything else in fiat-lux-agents (FilterBot, ChatBot, ExplorerBlueprint, etc.) is available but not currently wired in — easy additions for future features.

---

## The Entry Point: `agents/common/llm.py`

All AI calls in Libertas go through a single module:

```python
from fiat_lux_agents import LLMBase, SummaryBot

SONNET = "claude-sonnet-4-6"       # quality tasks: parsing, chat, reasoning
HAIKU  = "claude-haiku-4-5-20251001"  # speed/cost tasks: classification, filtering

def make_llm(model=SONNET, max_tokens=2048) -> LLMBase:
    return LLMBase(model=model, max_tokens=max_tokens)

def make_summary_bot(description: str) -> SummaryBot:
    return SummaryBot(dataset_description=description, model=SONNET)
```

Handlers import from here rather than touching fiat-lux-agents directly. This means model constants are defined once and model changes are a one-line edit.

---

## Where LLMBase Is Used

`LLMBase.call_api(system_prompt, messages)` is the core method — it handles the Anthropic API call, retries, and returns the response text.

| File | Feature | What it does |
|---|---|---|
| `agents/itinerary/parser.py` | Itinerary parsing | Parses uploaded PDFs, URLs, and text into structured trip data |
| `agents/itinerary/summarizer.py` | Trip summarization | Generates a plain-text summary of a trip for display |
| `agents/create/chat_handler.py` | Create chat | AI assistant for building trips via conversation |
| `agents/create/upload_handlers.py` | File upload parsing | Extracts itinerary data from uploaded files (PDF, Excel, Word, ICS) |
| `agents/explore/handler.py` | Explore chat | Recommends restaurants, hotels, and attractions for a destination |

### Model selection in practice

- **Sonnet** (`SONNET`) is used everywhere quality matters: parsing uploaded documents, the create chat loop, explore recommendations
- **Haiku** (`HAIKU`) is available in `llm.py` for speed/cost tasks — currently used as an override in specific classification steps

---

## When to use fiat-lux-agents vs. direct API calls

Not every LLM call in Libertas needs to go through fiat-lux-agents. A simple sidebar chat or one-off classification is fine as a direct `anthropic.messages.create()` call — adding fla indirection would just obscure what the code is doing.

**Use fiat-lux-agents (via `agents/common/llm.py`) when:**
- The feature involves a **tool use loop** (create chat, itinerary parsing with tool calls)
- The pattern would be **reused in another app** (summarization, explore chat)
- An **existing bot fits** (`SummaryBot`, `FilterBot`, `ExplorerBlueprint`)

**Go direct when:**
- Single-turn Q&A with data as context — e.g. a sidebar that just answers questions about a DataFrame
- App-specific one-off feature that won't be reused elsewhere

See the [fiat-lux-agents README](https://github.com/aabtzu/fiat-lux-agents#when-to-use-fiat-lux-agents) for the full decision guide.

---

## Adding a New AI Feature

1. Import from `agents/common/llm.py`, not directly from fiat-lux-agents:
   ```python
   from agents.common.llm import make_llm, SONNET, HAIKU
   ```

2. Instantiate in the handler, not in the route:
   ```python
   # In agents/myfeature/handler.py
   def my_handler(user_input: str) -> dict:
       llm = make_llm(model=SONNET)
       response = llm.call_api(SYSTEM_PROMPT, [{"role": "user", "content": user_input}])
       ...
   ```

3. Keep system prompts as module-level constants (same reason as SQL constants — readable and maintainable):
   ```python
   _SYSTEM_PROMPT = """
   You are a travel assistant. Given a destination, suggest...
   """
   ```

4. Never call `anthropic.Anthropic()` directly — always go through `LLMBase`.

---

## Using More of fiat-lux-agents

fiat-lux-agents has several other bots that could slot into Libertas naturally:

| Bot | Potential use |
|---|---|
| `FilterBot` + `FilterEngine` | Natural language filtering of the trips list or explore venue results |
| `ExplorerBlueprint` | Drop-in data explorer for venue analytics |
| `DocumentBot` | Richer rendering of uploaded itinerary documents |
| `WebSearchBot` | Live flight/hotel lookups during trip creation |

To add one, install the latest fiat-lux-agents, add a factory to `agents/common/llm.py`, and wire it into a handler.

---

## Installation

fiat-lux-agents is installed from GitHub via `requirements.txt`:

```
fiat-lux-agents @ git+https://github.com/aabtzu/fiat-lux-agents
```

For local development with changes to fiat-lux-agents itself, install editable:

```bash
pip install -e ~/repos/fiat-lux-agents
```

After any change to fiat-lux-agents, run both test suites:

```bash
.venv/bin/python3 -m pytest tests/ -x -q                              # libertas
.venv/bin/python3 -m pytest ~/repos/fiat-lux-agents/tests/ -x -q     # fiat-lux-agents
```
