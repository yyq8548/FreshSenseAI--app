# Development Log Update — LLM Reasoning Tool

## Milestone
Added GPT-ready LLM reasoning support with safe rule-based fallback.

## What Changed
- Added `tools/llm_reasoning.py`
- Added OpenAI SDK dependency
- Updated `FruitScannerAgent` to use `LLMReasoningTool`
- Added `source` field to `ReasoningResult`
- Updated Streamlit UI to show reasoning source
- Added fallback behavior when `OPENAI_API_KEY` is missing or API calls fail
- Added unit test for fallback behavior

## Why It Matters
The project now supports LLM-generated explanations while remaining robust when no API key is available. This makes the reasoning layer production-friendly because the application still works offline or when API calls fail.

## How to Enable LLM Reasoning

Set your API key locally:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-5"
```

Run:

```bash
python -m streamlit run app.py
```

## Interview Framing
I integrated an LLM reasoning layer behind a safe fallback interface. The agent first attempts to use GPT-based reasoning for explanation, storage advice, shelf-life estimation, and risk assessment. If the API key is missing or the request fails, it automatically falls back to the rule-based reasoning tool, preserving reliability.
