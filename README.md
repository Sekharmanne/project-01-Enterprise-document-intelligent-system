# Enterprise Document Intelligence System

## Configure the language model

Run the commands below from the project folder with the project's `env` Python environment installed. If you need a local configuration file, copy [`.env.example`](.env.example) to `.env`.

Add the API key for each provider you select. Groq is the default. Set `LLM_PROVIDER` to change the provider for document chat, analysis, and comparison. Each model variable is optional and accepts a model ID supported by the selected provider.

| Provider | `LLM_PROVIDER` | Model setting and default | API key |
| --- | --- | --- | --- |
| Groq | `groq` | `GROQ_CHAT_MODEL=qwen/qwen3.8-27b` | `GROQ_API_KEY` |
| OpenAI | `openai` | `OPENAI_CHAT_MODEL=gpt-4.1-mini` | `OPENAI_API_KEY` |
| Google Gemini | `google` | `GOOGLE_CHAT_MODEL=gemini-3.5-flash-lite` | `GOOGLE_API_KEY` |

Set `CHAT_LLM_PROVIDER` to override the provider for chat only. For example, `LLM_PROVIDER=groq` and `CHAT_LLM_PROVIDER=openai` use Groq for analysis and comparison and OpenAI for chat. Leave `CHAT_LLM_PROVIDER` blank in `.env` to have chat inherit `LLM_PROVIDER`.

Embeddings have their own settings. With the default `EMBEDDING_PROVIDER=huggingface`, set `HF_TOKEN` in `.env`.

### Save the selection in `.env`

For example, to use OpenAI for all three workflows, update these lines in `.env` and fill in `OPENAI_API_KEY`.

```dotenv
LLM_PROVIDER=openai
CHAT_LLM_PROVIDER=
OPENAI_CHAT_MODEL=gpt-4.1-mini
```

### Windows Command Prompt

Set the provider and model, then start the app in the same Command Prompt window.

```cmd
set "LLM_PROVIDER=openai"
set "OPENAI_CHAT_MODEL=gpt-4.1-mini"
env\Scripts\python.exe -m uvicorn app.main:app --port 8080
```

For Gemini, use `set "LLM_PROVIDER=google"` and `set "GOOGLE_CHAT_MODEL=gemini-3.5-flash-lite"` before the start command. To switch back to Groq, use `set "LLM_PROVIDER=groq"`. For a chat-only override, use `set "CHAT_LLM_PROVIDER=openai"`.

### Windows PowerShell

```powershell
$env:LLM_PROVIDER = "openai"
$env:OPENAI_CHAT_MODEL = "gpt-4.1-mini"
.\env\Scripts\python.exe -m uvicorn app.main:app --port 8080
```

For Gemini, set `$env:LLM_PROVIDER = "google"` and `$env:GOOGLE_CHAT_MODEL = "gemini-3.5-flash-lite"` before starting the app. To switch back to Groq, set `$env:LLM_PROVIDER = "groq"`. For a chat-only override, set `$env:CHAT_LLM_PROVIDER = "openai"`.

Console settings apply to the current terminal and take precedence over the corresponding values in `.env`. The app can still read API keys from `.env`. If the app is already running, stop it with **Ctrl+C**, make the change, and start it again. Open [the local app](http://localhost:8080) after startup.
