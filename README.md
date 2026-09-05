# Personal Fitness AI Assistant

A Streamlit fitness assistant for managing personal fitness profiles, saving profile-specific notes, generating nutrition targets, and asking AI-supported fitness questions through Langflow.

The project is built as a local/tutorial-friendly Python app with a clear backend boundary:

- Streamlit renders the app UI.
- Astra DB stores accounts, profile data, nutrition targets, and notes.
- Langflow orchestrates the AI workflows.
- OpenRouter is used by Langflow for model calls.

> This app provides general fitness planning information only. It is not medical advice.

## Features

- Username/password account creation and login.
- Logged-in account password updates.
- Profile create, view, edit, save, and cancel flows.
- Gender, activity level, and dynamic goals editing.
- Light and dark UI theme toggle.
- AI-generated nutrition/macros draft:
  - calories
  - protein
  - fat
  - carbs
- Manual nutrition review and save.
- Profile-scoped notes.
- Ask AI workflow with profile context and notes retrieval.
- Safe OpenRouter/Langflow error classification for quota, timeout, config, connection, HTTP, and response-shape failures.

## Architecture

```text
Streamlit UI
main.py
    |
    |-- auth.py
    |       |
    |       v
    |   Astra DB accounts collection
    |
    |-- profiles.py / db.py
    |       |
    |       v
    |   Astra DB
    |   - personal_data: profile and nutrition documents
    |   - notes: profile-scoped notes with Astra vectorize support
    |
    |-- ai.py
            |
            v
        Langflow API
        - Macro Flow -> OpenRouter -> JSON nutrition targets
        - Ask AI V2 -> router
              |-- math path
              |-- advice path with Astra note retrieval
```

The Streamlit app does not call OpenRouter directly. It calls Langflow, and Langflow calls OpenRouter.

## Project Structure

```text
.
|-- main.py                         # Streamlit UI and session flow
|-- auth.py                         # Account creation, login, password hashing/update
|-- ai.py                           # Langflow client and AI workflow helpers
|-- db.py                           # Astra DB access and data validation
|-- profiles.py                     # Profile-facing data helpers
|-- utils.py                        # Nutrition parsing and utility functions
|-- config.py                       # Environment variable contract
|-- flows/
|   |-- macro_flow.json             # Exported Langflow Macro Flow
|   `-- ask_ai_v2.json              # Exported Langflow Ask AI flow
|-- scripts/                        # Setup, smoke, and migration scripts
|-- tests/                          # Unit and regression tests
`-- docs/                           # Setup, security, compatibility, and state docs
```

## Prerequisites

- Python 3.11.
- Git.
- Astra DB with Data API access.
- Langflow running locally or remotely.
- OpenRouter credentials configured for the Langflow workflows.

Langflow is intentionally separate from this app's Python virtual environment. A common local setup is to run Langflow from `~/langflow-local` and run this Streamlit app from this repository.

## Setup

Create and activate a Python environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Fill `.env` with your local values. Do not commit real secrets.

## Environment Variables

Core application values:

```env
APP_ENV=development
```

Astra DB:

```env
ASTRA_DB_API_ENDPOINT=
ASTRA_DB_APPLICATION_TOKEN=
ASTRA_DB_KEYSPACE=
ASTRA_PERSONAL_COLLECTION=personal_data
ASTRA_NOTES_COLLECTION=notes
ASTRA_ACCOUNTS_COLLECTION=accounts
```

Langflow:

```env
LANGFLOW_URL=http://127.0.0.1:7860
LANGFLOW_API_KEY=
MACRO_FLOW_ID=
ASK_AI_FLOW_ID=
MACRO_PROFILE_COMPONENT_ID=
MACRO_GOALS_COMPONENT_ID=
ASK_PROFILE_COMPONENT_ID=
ASK_USER_ID_COMPONENT_ID=
```

OpenRouter/Langflow runtime tuning:

```env
OPENROUTER_API_KEY=
MACRO_OPENROUTER_COMPONENT_ID=ext:openrouter:OpenRouterComponent@official-snoVc
ASK_ROUTER_OPENROUTER_COMPONENT_ID=ext:openrouter:OpenRouterComponent@official-lyVR9
ASK_ADVICE_OPENROUTER_COMPONENT_ID=ext:openrouter:OpenRouterComponent@official-N7r20
ASK_MATH_AGENT_COMPONENT_ID=Agent-8TtHH
MACRO_OPENROUTER_MAX_TOKENS=512
ASK_ROUTER_OPENROUTER_MAX_TOKENS=128
ASK_ADVICE_OPENROUTER_MAX_TOKENS=1024
ASK_MATH_AGENT_MAX_TOKENS=512
```

`LANGFLOW_API_KEY` is the key for calling Langflow. `OPENROUTER_API_KEY` is the key Langflow uses for OpenRouter model calls when passed through runtime tweaks.

## Langflow Setup

Import these exported flows into Langflow:

- `flows/macro_flow.json`
- `flows/ask_ai_v2.json`

Then copy the real flow IDs and component IDs into `.env`.

The expected Langflow API contract is:

- endpoint: `/api/v1/run/<flow_id>`
- auth header: `x-api-key`
- input type: `chat`
- output type: `chat`
- runtime tweaks keyed by Langflow component ID

For detailed flow construction and component references, see [docs/LANGFLOW_SETUP.md](docs/LANGFLOW_SETUP.md).

## Running Locally

Start Langflow in its own terminal:

```bash
deactivate
cd ~/langflow-local
source .venv/bin/activate
langflow run --host 127.0.0.1 --port 7860
```

Start the Streamlit app in this repository:

```bash
source .venv/bin/activate
streamlit run main.py
```

Open the local URL printed by Streamlit, usually:

```text
http://localhost:8501
```

## Validation and Tests

Check configuration without printing secrets:

```bash
python scripts/check_config.py --mode all
```

Run the safe test suite:

```bash
python -m pytest
```

Run compile checks:

```bash
python -m compileall main.py auth.py profiles.py db.py ai.py utils.py config.py
```

Useful setup and smoke scripts:

```bash
python scripts/check_astra.py
python scripts/setup_accounts_collection.py
python scripts/setup_personal_collection.py
python scripts/setup_notes_collection.py
python scripts/test_macro_flow.py
```

Some scripts call live services. Review the script before running it against real data.

## Security Notes

- Passwords are hashed with Argon2id.
- Raw passwords are not stored in account documents.
- `.env` must remain local and untracked.
- Error handling avoids showing raw secrets, provider payloads, API keys, or password hashes to users.
- Langflow and OpenRouter credentials should remain server-side.
- This project is suitable for local development and private use. Public multi-user deployment needs a full production security review.

See [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md) and [docs/DEPLOYMENT_READINESS.md](docs/DEPLOYMENT_READINESS.md) for more detail.

## Troubleshooting

### Missing Environment Variable

Run:

```bash
python scripts/check_config.py --mode all
```

Then fill the missing value in `.env`.

### Langflow Cannot Be Reached

Confirm Langflow is running:

```bash
curl http://127.0.0.1:7860/api/v1/version
```

If Streamlit and Langflow are not on the same machine, `127.0.0.1` will not work. Use a reachable HTTPS Langflow URL.

### Langflow 401 or 403

Check `LANGFLOW_API_KEY`. It must be a Langflow API key, not an OpenRouter key.

### Langflow 404

Check `MACRO_FLOW_ID` and `ASK_AI_FLOW_ID`.

### OpenRouter Credit or Token-Budget Error

The app caps OpenRouter model output tokens through Langflow tweaks. If you still see a quota/token-budget error:

- verify `OPENROUTER_API_KEY`
- confirm the key has usable OpenRouter credits
- lower the `*_OPENROUTER_MAX_TOKENS` values in `.env`
- confirm the OpenRouter component IDs match your imported Langflow flows

### Macro Output Is Not Valid JSON

The Macro Flow must return only JSON with:

```json
{
  "calories": 2200,
  "protein": 150,
  "fat": 70,
  "carbs": 250
}
```

Fix the Langflow prompt/model behavior rather than weakening the parser.

## Documentation

- [Langflow setup](docs/LANGFLOW_SETUP.md)
- [Acceptance tests](docs/ACCEPTANCE_TESTS.md)
- [Compatibility audit](docs/COMPATIBILITY.md)
- [Security review](docs/SECURITY_REVIEW.md)
- [Deployment readiness](docs/DEPLOYMENT_READINESS.md)
- [Build state](docs/BUILD_STATE.md)
- [UI update state](docs/UI_UPDATE_STATE.md)

## License

No license file is currently included. Add one before distributing or publishing this project.
