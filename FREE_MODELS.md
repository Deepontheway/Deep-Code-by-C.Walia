## Free Models

Free OpenCode online models need no API key. They are `big-pickle` plus every model ending in `-free`. The app loads the current list from OpenCode automatically.

- big-pickle (default, free, no key)
- deepseek-v4.1-flash-free (free, no key)
- glm-5.3-flash-free (free, no key)
- nemotron-3.5-lightning-free (free, no key)
- nemotron-3.5-super-vl-free (free, no key)
- mimo-v2.6-flash-free (free, no key)
- flint-40b-free (free, no key)
- beam-free (free, no key)
- jev-1.13-free (free, no key)
- qwen2.5-coder:14b (local via Ollama, free, no key)
- qwen2.5-coder:32b (local via Ollama, free, no key)
- deepseek-coder-v2:16b (local via Ollama, free, no key)
- openai-fast (Pollinations, free, no key, automatic fallback)

Paid online models such as Claude, GPT, Gemini, Grok, and Qwen Plus require an API key. If a free model hits its anonymous usage limit, the app automatically retries another OpenCode free model, then falls back to the keyless Pollinations model at `https://text.pollinations.ai/v1`. Use Settings to switch models at any time.

If a local Ollama model returns 404, the model name is not installed. Open Settings and pick one of the detected local models, or run `ollama pull qwen2.5-coder:14b`.
