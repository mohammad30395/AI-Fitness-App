# Compatibility Audit

Audit date/time: 2026-08-14 01:06:32 +0600 +06

This audit records the known working local environment for the tutorial-compatible Personal Fitness AI Assistant. It preserves the current architecture: Streamlit app, Langflow orchestration, OpenRouter inside Langflow, and Astra DB for profile data and vectorized notes.

## Known Working Environment

| Item | Current value |
| --- | --- |
| Python executable | `.venv/bin/python` |
| Python version | 3.11.15 |
| Platform | macOS-26.6.1-arm64-arm-64bit |
| CPU architecture | arm64 |
| Streamlit | 1.61.1 |
| astrapy | 2.3.1 |
| python-dotenv | 1.2.2 |
| requests | 2.34.2 |
| pytest | 9.1.1 |
| Langflow export tested version | 1.11.3 |

## Package Compatibility

Official PyPI release metadata reports these Python requirements:

| Package | Installed version | Requires Python |
| --- | ---: | --- |
| streamlit | 1.61.1 | >=3.10 |
| astrapy | 2.3.1 | >=3.10,<4.0 |
| python-dotenv | 1.2.2 | >=3.10 |
| requests | 2.34.2 | >=3.10 |
| pytest | 9.1.1 | >=3.10 |

Python 3.11.15 satisfies these requirements.

Dependency decision: `requirements.txt` and `requirements-dev.txt` are pinned to the exact direct packages currently working in this local project. Transitive packages are intentionally not listed manually.

## Streamlit APIs

`main.py` uses `st.set_page_config`, `st.session_state`, forms, inputs, buttons, spinners, markdown/text rendering, and standard layout primitives. The installed Streamlit exposes `st.fragment`, but the current app does not depend on it. The shell remains correct under normal Streamlit reruns through explicit `st.session_state` initialization.

## Astra DB and astrapy

The installed `astrapy` provides `DataAPIClient` from `astrapy`. The current project uses:

- `DataAPIClient(token)`
- `client.get_database(api_endpoint, keyspace=...)` when a keyspace is configured
- `database.get_collection(...)`
- `database.list_collection_names()`
- collection `insert_one`, `find`, `find_one`, `update_one`, and `delete_one`

`ASTRA_DB_KEYSPACE` remains configurable and may be empty if the current Data API usage does not require it.

## Astra Vectorize

The `notes` collection is vectorize-enabled and stores readable note text in `text`. Inserts send note text through `$vectorize`; the generated `$vector` is managed by Astra.

Current vectorize configuration observed from the live database:

- Collection: `notes`
- Provider: `nvidia`
- Model: `nvidia/nv-embedqa-e5-v5`
- Dimension: `1024`
- Metric: `cosine`

Ask AI V2 retrieval uses the `text` content field and a runtime metadata filter for `user_id`.

## Langflow Runtime Contract

The current Langflow API contract differs from older tutorial-era Bearer-token examples.

Current contract:

- Base URL: configured by `LANGFLOW_URL`
- Run path: `/api/v1/run/<flow_id>`
- Auth header: `x-api-key`
- `input_type`: `chat`
- `output_type`: `chat`
- `tweaks`: component-id keyed object
- Response text extraction path used by the Python client: `outputs[0].outputs[0].results.message.text`

Macro Flow:

- Flow ID is configured locally by `MACRO_FLOW_ID`.
- Profile context is sent as `input_value`.
- Goals are sent through `Prompt Template-VgARU.goals`.
- OpenRouter model inside Langflow: `openai/gpt-4o-mini`, temperature `0`.

Ask AI V2:

- Flow ID is configured locally by `ASK_AI_FLOW_ID`.
- Question is sent as `input_value`.
- Profile context is sent through `Prompt Template-GtOCM.profile`.
- User isolation is sent through `ext:datastax:AstraDBVectorStoreComponent@official-2VBhC.advanced_search_filter`.
- The filter value is a JSON string such as `{"user_id":"selected-profile-id"}`.
- OpenRouter model inside Langflow: `openai/gpt-4o-mini`, temperature `0`.

## Compatibility Notes

- OpenRouter credentials remain inside Langflow or local environment configuration, not in app source.
- Streamlit does not call OpenRouter directly.
- Python does not perform Ask AI routing or vector search; Langflow owns those paths.
- Python note writes include `$vectorize` and never manually generate `$vector`.
- Note list/delete/update operations are scoped by `user_id`.

## Validation

Validation commands required for this audit:

- `pip check`
- `pytest -q`
- `python -m compileall` excluding virtual environments
- non-destructive Astra connectivity/vectorize smoke
- non-destructive Langflow Macro Flow smoke
- non-destructive Langflow Ask AI math smoke

Results are recorded in `docs/BUILD_STATE.md`.

Latest results:

| Check | Result |
| --- | --- |
| `pip check` | PASS: no broken requirements found |
| `pytest -q` | PASS: 109 tests passed |
| `python -m compileall` excluding `.venv` and `__pycache__` | PASS |
| Astra connectivity smoke | PASS: `notes` and `personal_data` collections accessible |
| Astra vectorize smoke | PASS: `notes` uses provider `nvidia` and model `nvidia/nv-embedqa-e5-v5` |
| Macro Flow smoke | PASS: returned parseable nutrition JSON with calories/protein/fat/carbs |
| Ask AI math smoke | PASS: returned a numerically coherent answer containing `108` |
