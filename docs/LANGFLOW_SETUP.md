# Langflow Setup

This file records the real Langflow setup used by this project. It does not contain secrets.

Langflow is installed separately from the project `.venv` and was running locally at:

```text
http://127.0.0.1:7860
```

## Macro Flow

Status: built manually in the Langflow UI and exported from Langflow.

Exported file:

```text
flows/macro_flow.json
```

### Topology

The final flow is logically:

```text
profile Chat Input -> Prompt Template -> OpenRouter -> Chat Output
                         ^
                         |
                       goals
```

The current Langflow installation did not expose a reusable `Text Input` component and allowed only one `Chat Input`, so the profile context is passed through the chat input runtime value and the goals text is an API-exposed Prompt Template field.

### Components

Real component IDs from the exported flow:

- Profile runtime input: `ChatInput-RkQmU`
- Prompt Template: `Prompt Template-VgARU`
- OpenRouter model: `ext:openrouter:OpenRouterComponent@official-snoVc`
- Output: `ChatOutput-mqlKE`

### Prompt

The Prompt Template uses `profile` and `goals` variables and instructs the model to return only valid JSON:

```text
You are generating approximate daily nutrition targets for a personal fitness assistant.

Use the profile and goals below to estimate general fitness guidance. These are approximate planning targets, not medically precise nutrition advice.

Return ONLY valid JSON.

Do not include markdown.
Do not include code fences.
Do not include explanations.
Do not include comments.
Do not include units inside the values.
Do not include additional keys.

The JSON object must contain exactly:

{{ "calories": number, "protein": number, "fat": number, "carbs": number }}

Profile:
{profile}

Goals:
{goals}
```

### Model

Provider/component:

```text
OpenRouter
```

Model selected from the available OpenRouter model list:

```text
openai/gpt-4o-mini
```

Settings:

- Temperature: `0`
- System message: `Return only valid JSON for approximate fitness macro targets. No markdown or extra text.`
- API key configured securely in Langflow and not saved into the exported flow.

### Playground Verification

Three synthetic Playground tests succeeded. Each returned parseable JSON with exactly these numeric keys:

- `calories`
- `protein`
- `fat`
- `carbs`

Sanitized observed examples:

```json
{ "calories": 2800, "protein": 180, "fat": 70, "carbs": 350 }
{ "calories": 2200, "protein": 160, "fat": 70, "carbs": 250 }
{ "calories": 2500, "protein": 150, "fat": 70, "carbs": 350 }
```

An earlier `openai/gpt-4o` test failed with OpenRouter `402`, so the flow was switched to `openai/gpt-4o-mini`.

### API Contract

The real Share -> API Access snippet showed:

```text
API version: v1
URL: http://127.0.0.1:7860/api/v1/run/d0c80780-b504-471e-bc25-f203987baad3
Auth header: x-api-key
input_type: chat
output_type: chat
```

Flow ID:

```text
d0c80780-b504-471e-bc25-f203987baad3
```

Runtime field strategy for the later `ai.py` integration:

- `profile` should be sent as the normal chat `input_value`.
- `goals` should be sent by tweaking the Prompt Template component field named `goals` on component `Prompt Template-VgARU`.

The generated Python snippet visible in the UI did not include an explicit `tweaks` block even after exposing the `goals` field through Parameters. The actual component ID and field name above were verified from the exported Langflow JSON instead of guessed.

Expected request shape for the later integration, subject to a live API smoke test during the `ai.py` milestone:

```python
payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": profile_context,
    "tweaks": {
        "Prompt Template-VgARU": {
            "goals": goals_text
        }
    },
}
headers = {"x-api-key": langflow_api_key}
```

Response extraction must be confirmed against the live API response during the integration milestone. Do not assume an old tutorial response parser without testing this Langflow version.

### Environment Variables

Set these in local `.env` before implementing the Python Langflow integration:

```env
LANGFLOW_URL=http://127.0.0.1:7860
LANGFLOW_API_KEY=
MACRO_FLOW_ID=d0c80780-b504-471e-bc25-f203987baad3
MACRO_PROFILE_COMPONENT_ID=ChatInput-RkQmU
MACRO_GOALS_COMPONENT_ID=Prompt Template-VgARU
```

`LANGFLOW_API_KEY` must be a Langflow API key, not the OpenRouter API key. Real secrets remain in `.env` only.

### Guardrails

- The flow was built in the real Langflow UI.
- `flows/macro_flow.json` came from Langflow export.
- `Save with my API keys` was left unchecked during export.
- Export inspection found no obvious OpenRouter or Astra secret strings.
- `ai.py`, `get_macros()`, Ask AI V2, and Streamlit UI were not implemented in this milestone.
