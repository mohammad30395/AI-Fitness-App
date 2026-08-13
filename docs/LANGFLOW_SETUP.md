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

### Export Validation

Validated exported file:

```text
flows/macro_flow.json
```

Export metadata:

- Flow ID: `d0c80780-b504-471e-bc25-f203987baad3`
- Flow name: `Macro Flow`
- Endpoint name: not configured
- Langflow export tested version: `1.11.3`

Confirmed graph edges:

- `ChatInput-RkQmU` -> `Prompt Template-VgARU.profile`
- `Prompt Template-VgARU` -> `ext:openrouter:OpenRouterComponent@official-snoVc.input_value`
- `ext:openrouter:OpenRouterComponent@official-snoVc` -> `ChatOutput-mqlKE.input_value`

Confirmed runtime fields:

- API `input_value`: profile context text
- Tweak component ID for goals: `Prompt Template-VgARU`
- Tweak field for goals: `goals`

Tutorial-era assumptions not used:

- Do not use Bearer auth for this local v1 flow unless a future generated snippet says so. The current generated snippet uses `x-api-key`.
- Do not assume an older response parser shape from a tutorial. The visible generated snippet prints `response.text`; the exact nested extraction path must be confirmed with a live call during the HTTP integration milestone.
- Do not assume separate `Text Input` components exist in this Langflow UI. This export uses `ChatInput` for profile and a Prompt Template API field for goals.

Current validation blocker:

- Langflow was not reachable at `http://127.0.0.1:7860` during this repository validation pass, so no live API response body was captured in this step.

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

## Ask AI V2

Status: manual build guide only. Do not generate or import assistant-created Langflow JSON for this flow.

The intended flow is a routed workflow with two paths:

```text
Question Input
    |
    v
Router Prompt -> OpenRouter model -> Conditional Router
    | math / yes                 | non-math / no
    v                            v
Agent with Calculator            Astra DB vector search
    |                            filtered by user_id
Calculator Tool                  |
    |                            v
    v                            Parser / text context
Math Output                      |
                                 v
                         Advice Prompt Template
                         inputs: question, profile, notes
                                 |
                                 v
                         OpenRouter model
                                 |
                                 v
                         Advice Output
```

### Component Roles

Use the component names visible in the current Langflow editor. In this Langflow version, the likely current names are:

- Question input: `Chat Input`
- Router prompt: `Prompt Template`
- Router model: `OpenRouter`
- Conditional router: `If-Else` if you are routing on the literal output `yes`; use `Smart Router` only if your UI makes that the supported routing component for model categories.
- Math path: `Agent` with a real `Calculator` tool connected to the Agent tools input.
- RAG path: `Astra DB` from the DataStax bundle for vector search against the existing `notes` collection.
- Notes-to-text transformation: `Parser` or the current parsing component that extracts note text into context.
- Advice prompt: `Prompt Template`
- Advice model: `OpenRouter`
- Output: `Chat Output` or `Text Output`, whichever works in your Playground/API Access for this flow.

Do not call the RAG path an autonomous agent. It is a normal retrieval-and-generation chain.

### Runtime Inputs

The later Python app needs to provide these runtime values:

- `question`: the user's question, preferably through the normal chat/API `input_value`.
- `profile`: profile context from `profiles.build_profile_context(...)`, exposed through a Prompt Template field or equivalent runtime tweak.
- `user_id`: selected profile ID, used in the Astra DB vector search filter so notes never mix between profiles.

Use existing placeholder variables in `.env.example` after the real flow is exported:

```env
ASK_AI_FLOW_ID=
ASK_PROFILE_COMPONENT_ID=
ASK_USER_ID_COMPONENT_ID=
```

Do not fill these with guessed values. Copy actual IDs only from Share -> API Access or the real exported Langflow JSON after you manually build and export the flow.

### Router Path

Add the question input, router Prompt Template, OpenRouter model, and conditional router.

Router Prompt Template:

```text
Classify whether the user's question requires calculator/tool reasoning.

Return only one lowercase word:
yes
no

Return yes only when arithmetic, unit conversion, macro totals, calorie math, BMI-style arithmetic, date arithmetic, or another explicit calculation is required.

Return no for general fitness, nutrition, profile, habit, or note-based advice that does not require calculation.

Question:
{question}
```

Router model settings:

- Provider: `OpenRouter`
- Model: choose a currently available OpenRouter chat model from the real model list.
- Temperature: `0`
- System message, if available:

```text
Return only yes or no.
```

Conditional router configuration:

- If using `If-Else`, compare the router model output to `yes`.
- True/yes path goes to the math Agent.
- False/no path goes to Astra DB vector search.
- Do not route on vague prose. If the router emits anything except `yes` or `no`, fix the router prompt/model settings before wiring Python.

### Math Path

Add one real `Agent` component and one real `Calculator` tool.

Configuration:

- Use the current Langflow `Agent` component. The current Agent component supports tool calling when tools are connected.
- Add the `Calculator` component.
- Connect the Calculator tool output to the Agent tools input.
- Do not fake calculator behavior with a prompt-only model.
- Do not add extra tools for this milestone.

Math Agent instruction:

```text
You answer only calculation-based fitness questions.
Use the calculator tool for arithmetic.
Return a concise answer with the calculation result and a short plain-language explanation.
Do not provide medical diagnosis.
```

Connect the math path to `Math Output`.

### RAG Advice Path

Add an Astra DB vector search component from the DataStax bundle.

Use the existing Astra DB setup:

- Collection: `notes`
- Raw readable note field: `text`
- Server-side vectorize collection: the collection was created with Astra-managed `$vectorize`/`$vector`.
- Search query: user question text.
- Filter: selected profile/user ID only.

The exact Astra DB component fields vary by Langflow/DataStax bundle version. Inspect the component parameters instead of guessing. Configure the user filter semantically as:

```json
{ "user_id": "<runtime selected profile id>" }
```

Expose the actual field carrying that filter or user ID through Parameters/API so the Python app can pass the selected profile ID at runtime.

Do not:

- Create a new Astra collection.
- Insert sample notes.
- Guess vector dimensions.
- Add manual `$vector` values.
- Remove the user_id filter.

After Astra search, add a parsing component to extract readable note text. Use the current `Parser` or equivalent component to turn retrieved documents into concise text context for the advice prompt.

### Advice Prompt

Add a Prompt Template for the non-math advice path.

Template:

```text
You are a personal fitness assistant providing general fitness and nutrition guidance.

Use the profile context, retrieved notes, and user question below.

Safety:
- Provide general fitness information only.
- Do not claim medical precision.
- Do not diagnose injuries or medical conditions.
- Do not treat or prescribe.
- Recommend professional medical evaluation for significant pain, injury, alarming symptoms, eating disorder concerns, pregnancy-specific medical questions, medication interactions, or other urgent/clinical issues.

Profile context:
{profile}

Retrieved note context:
{notes}

User question:
{question}

Answer clearly and practically. If the retrieved notes are empty or unrelated, say that you do not have relevant notes and answer from the profile and general guidance only.
```

Inputs required by this prompt:

- `question`
- `profile`
- `notes`

Connect:

- Question input -> Advice Prompt `question`
- Profile runtime value -> Advice Prompt `profile`
- Parsed Astra note context -> Advice Prompt `notes`
- Advice Prompt -> OpenRouter model -> Advice Output

Advice model settings:

- Provider: `OpenRouter`
- Model: choose only from the models actually available in the current Langflow/OpenRouter model list.
- Temperature: `0` to `0.3`
- Keep OpenRouter credentials in Langflow/global variables, not source code.

### Manual Test Checklist

Use synthetic test data only.

Math test:

```text
If my calorie target is 2400 and I ate 650 breakfast plus 780 lunch, how many calories remain?
```

Expected route:

- Router returns `yes`.
- Agent uses Calculator.
- Output answers the arithmetic question.

Advice/RAG test:

```text
Based on my profile and notes, how should I structure my next workout week?
```

Expected route:

- Router returns `no`.
- Astra DB vector search runs with a `user_id` filter.
- Advice prompt receives question, profile, and retrieved note context.
- Output gives general advice with safety-aware wording.

Use a known safe test note that already exists for the selected synthetic/test profile, or create one through the application's explicit note smoke-test tooling before testing. Do not insert production sample notes from Langflow during this milestone.

Isolation test:

- Run the advice path with a different synthetic/test profile ID.
- Confirm the first profile's known test note is not retrieved for the second profile.
- If notes appear across profiles, stop and fix the Astra DB filter before exporting the flow.

### API Access And Export

After the flow works in Playground:

1. Expose only the runtime/API fields needed by the Python app:
   - profile context
   - selected user/profile ID for the Astra filter
   - any required question field if it is not supplied through the normal API `input_value`
2. Open Share -> API Access.
3. Capture the actual generated contract:
   - flow ID or endpoint
   - auth header
   - input/output types
   - response shape
   - actual tweak component IDs and field names
4. Do not assume Bearer auth if the generated snippet uses `x-api-key`.
5. Save the actual generated API snippet in a safe local reference only after redacting any real API key.
6. Export the completed real flow from Langflow.
7. Save it as `flows/ask_ai_v2.json` only after it comes from Langflow's real export function.
8. Keep `Save with my API keys` unchecked.
9. Stop and wait for confirmation before implementing Python integration.

Do not implement Python integration for Ask AI V2 until the real API contract and exported flow are inspected.

### Completion Gate

This milestone is not complete until all of these are true:

- The flow was manually built in the current Langflow visual editor.
- No assistant-generated Langflow JSON was imported.
- The router returns deterministic `yes` or `no`.
- A pure arithmetic question routes to the Calculator Agent path.
- A fitness advice question routes to the Astra RAG path and retrieves a known note for the selected test profile.
- A question from a different profile does not retrieve the first profile's note.
- Only models actually available in the current Langflow/OpenRouter installation were selected.
- Share/API Access was inspected.
- Only required runtime fields were exposed.
- The actual generated API snippet was saved safely with secrets redacted.
- The real exported flow was saved as `flows/ask_ai_v2.json`.
- No component IDs were invented.
- `ai.py` was not modified for Ask AI V2 yet.

References checked:

- Langflow components overview: https://docs.langflow.org/concepts-components
- Agent and tool calling: https://docs.langflow.org/agents and https://docs.langflow.org/agents-tools
- If-Else conditional router: https://docs.langflow.org/if-else
- Smart Router: https://docs.langflow.org/smart-router
- DataStax/Astra DB bundle: https://docs.langflow.org/bundles-datastax
- Vector RAG and Parser role: https://docs.langflow.org/knowledge
- API key auth: https://docs.langflow.org/api-keys-and-authentication
