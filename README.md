# Personal Fitness AI Assistant

A tutorial-compatible local fitness assistant built with Python, Streamlit, Langflow, OpenRouter, and Astra DB.

The app lets you manage profile documents, store profile-scoped fitness notes, generate approximate macro targets through a Langflow Macro Flow, and ask routed fitness questions through Ask AI V2. OpenRouter stays inside Langflow. Astra DB stores structured profile data and vectorized notes.

## Architecture

```text
Streamlit UI (main.py)
    |
    |-- profiles.py / db.py
    |       |
    |       v
    |   Astra DB
    |   - personal_data: structured profile documents
    |   - notes: readable note text + user_id + Astra-managed vectors
    |
    |-- ai.py
            |
            v
        Langflow API
        - Macro Flow -> OpenRouter model -> JSON macro targets
        - Ask AI V2 -> router
              |-- math path: one Tool Calling Agent + Calculator
              |-- advice path: Astra RAG chain filtered by user_id
```

## Prerequisites

- macOS or another local development machine with Python 3.11.
- Git.
- A local or hosted Astra DB database with Data API access.
- A normal profile collection, default `personal_data`.
- A vectorize-enabled notes collection, default `notes`.
- Langflow running separately from this app environment, locally or in the cloud.
- OpenRouter configured inside Langflow.

Langflow is intentionally not installed into this app `.venv` by default. It may run in a separate environment or in Langflow Cloud.

## Local Python Environment

Commands used for this project:

```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

If your Python 3.11 executable is in a different location, use that executable for the `venv` command.

## Environment Setup

Create your local `.env` from the placeholder file:

```bash
cp .env.example .env
```

Fill in real values only in `.env`. Do not commit `.env`.

Then verify configuration names without printing secrets:

```bash
python scripts/check_config.py --mode all
```

## Astra DB Setup

Required local values include:

- `ASTRA_DB_API_ENDPOINT`
- `ASTRA_DB_APPLICATION_TOKEN`
- `ASTRA_DB_KEYSPACE`, if your database requires it
- `ASTRA_PERSONAL_COLLECTION`, default `personal_data`
- `ASTRA_NOTES_COLLECTION`, default `notes`

Run the non-destructive Astra check:

```bash
python scripts/check_astra.py
```

Collection setup scripts are idempotent and do not drop collections:

```bash
python scripts/setup_personal_collection.py
python scripts/setup_notes_collection.py
```

The notes collection is expected to use Astra server-side vectorize. See [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for the exact known working provider/model.

## Langflow Setup

Import or rebuild the real exported flows in Langflow:

- `flows/macro_flow.json`
- `flows/ask_ai_v2.json`

OpenRouter credentials must be configured securely inside Langflow. Do not put OpenRouter keys in source code.

The current local Langflow API contract uses:

- URL path: `/api/v1/run/<flow_id>`
- Auth header: `x-api-key`
- `input_type`: `chat`
- `output_type`: `chat`
- `tweaks`: component-ID keyed runtime settings

Record your local flow IDs, Langflow API key, and required component IDs in `.env`. Use [docs/LANGFLOW_SETUP.md](docs/LANGFLOW_SETUP.md) as the source of truth.

## First Run Checklist

1. Activate the virtual environment:

```bash
source .venv/bin/activate
```

2. Verify configuration:

```bash
python scripts/check_config.py --mode all
```

3. Verify Astra:

```bash
python scripts/check_astra.py
```

4. Verify Macro Flow:

```bash
python scripts/test_macro_flow.py
```

5. Verify Ask AI Flow with disposable synthetic records:

```bash
python scripts/live_acceptance.py
```

6. Start Streamlit:

```bash
streamlit run main.py
```

## Local Run

```bash
streamlit run main.py
```

Open the local URL Streamlit prints in the terminal.

## Troubleshooting

- `Missing required environment variable`: fill that variable in `.env`, then rerun `python scripts/check_config.py --mode all`.
- Astra auth or connection failure: verify the database is active, the endpoint matches Astra Portal, the token has Data API access, and the keyspace is correct.
- Langflow `401` or `403`: verify `LANGFLOW_API_KEY`; the current API contract uses `x-api-key`.
- Langflow `404`: verify the flow ID in `.env`.
- Macro Flow returns prose instead of JSON: fix the Langflow prompt/model configuration. Do not weaken the parser.
- Ask AI does not retrieve notes: verify the `notes` collection, the vectorize model, and the `user_id` search metadata filter in Langflow.
- Cross-profile note leakage: stop using the app until the Ask AI V2 `user_id` filter is fixed and privacy-isolation tests pass.

## Documentation

- [Langflow setup](docs/LANGFLOW_SETUP.md)
- [Acceptance tests](docs/ACCEPTANCE_TESTS.md)
- [Security review](docs/SECURITY_REVIEW.md)
- [Compatibility audit](docs/COMPATIBILITY.md)
- [Build state](docs/BUILD_STATE.md)

## What This App Is Not

- Not medical diagnosis or clinical nutrition advice.
- Not real multi-user authentication.
- Not a peer-to-peer multi-agent system.
- Not a direct OpenRouter client from Streamlit.
