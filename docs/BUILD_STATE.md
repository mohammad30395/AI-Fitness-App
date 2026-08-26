# Build State

## Milestone

Current milestone: COMPLETE - final local-use preparation passed.

Next milestone: local use, optional deployment planning, or future feature work by explicit approval.

## Audit Date/Time

2026-08-13 11:55:31 +06 +0600

## Platform

- OS: macOS 26.6.1, build 25G76
- Kernel: Darwin 25.6.0
- CPU architecture: arm64

## Repository Status

- Git repository: yes
- Repository root: /Users/macbook/Desktop/Fahmid/Target/7.AI App/2.Date.13.08.2026/AI-Fitness-App
- Branch status: main tracking origin/main
- Working tree notes: .DS_Store is untracked

## Files Already Present

Top-level files/directories detected during audit:

- .DS_Store
- .git/
- .gitattributes
- docs/

Tracked files:

- .gitattributes

Target tutorial files:

- main.py: missing
- ai.py: missing
- db.py: missing
- profiles.py: missing
- config.py: missing
- requirements.txt: missing
- .env: missing, contents not read or printed

## Python And Tooling

Python interpreters detected:

- /usr/bin/python3 -> /Applications/Xcode.app/Contents/Developer/usr/bin/python3, Python 3.9.6
- /opt/homebrew/bin/python3.11 -> /opt/homebrew/opt/python@3.11/bin/python3.11, Python 3.11.15

Chosen Python executable:

- /opt/homebrew/opt/python@3.11/bin/python3.11

Reason:

- Python 3.11 is compatible with the current Python 3.10+ requirements documented for Streamlit, AstraPy, Requests, and Langflow, while the detected Apple/Xcode Python 3.9.6 is below those current requirements.

Package/tool commands detected:

- pip3: /usr/bin/pip3, pip 21.2.4 for Python 3.9
- Python 3.11 pip: pip 26.1.2 for Python 3.11
- git: /usr/bin/git, git version 2.50.1 (Apple Git-155)
- uv: not detected
- langflow: not detected

Virtual environments detected:

- None found under repository depth 3

## Blockers

- No blockers for this audit milestone.
- For the next milestone, create an isolated virtual environment using Python 3.11.15 before installing dependencies.
- uv is not currently detected; if using the current Langflow OSS recommended install path, install or otherwise account for uv during environment bootstrap.

## Guardrails Observed

- No packages installed.
- No Langflow flows created.
- No Astra DB collections created.
- No credentials created, modified, read, or printed.

## Environment Bootstrap

Bootstrap date/time:

- 2026-08-13 12:05:24 +06 +0600

Virtual environment:

- Path: .venv/
- Created with: /opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
- Runtime Python: Python 3.11.15
- pip upgraded inside .venv to: pip 26.2.1

Dependency files:

- requirements.txt contains application dependencies only: streamlit, astrapy, python-dotenv, requests
- requirements-dev.txt contains: pytest

Langflow decision:

- Langflow was not installed into .venv by default. This application architecture uses Streamlit for the app runtime and Langflow for AI orchestration, which may run in a separate local environment or in the cloud.

Direct installed package versions:

- streamlit==1.61.1
- astrapy==2.3.1
- python-dotenv==1.2.2
- requests==2.34.2
- pytest==9.1.1

Verification results:

- .venv/bin/python --version: Python 3.11.15
- .venv/bin/python -m pip check: No broken requirements found.
- Import smoke test: streamlit, astrapy, dotenv, and requests imported successfully.

Environment bootstrap guardrails:

- No LLM provider SDK was added as a direct application dependency.
- Langflow was not installed into .venv.
- No application logic created.
- No Astra DB collections created.
- No Langflow flows created.
- No credentials invented, created, modified, read, or printed.

## Configuration Handling

Configuration milestone date/time:

- 2026-08-13 12:26:36 +06 +0600

Files added:

- .env.example
- config.py
- scripts/check_config.py
- tests/test_config.py

Configuration decisions:

- config.py calls load_dotenv() and reads values with os.getenv.
- Base app configuration has no credential requirement yet.
- Astra validation requires Astra endpoint, token, and collection names.
- ASTRA_DB_KEYSPACE is optional because current AstraPy Data API usage may not require an explicit keyspace.
- Langflow validation requires the Langflow URL, API key, flow IDs, and component IDs needed by the tutorial architecture.
- OPENROUTER_API_KEY is included only as a future optional placeholder because the Streamlit app should call Langflow, not OpenRouter, in this architecture.
- Validation reports missing variable names only and never prints secret values.

Configuration verification:

- .venv/bin/python -m pytest: 3 passed
- .venv/bin/python scripts/check_config.py --mode base: passed
- git check-ignore -v .env: .env is ignored by .gitignore

Configuration guardrails:

- No fake keys added.
- No .env file created.
- No external service connection attempted.
- No Astra DB collections created.
- No Langflow flows created.
- No application logic created.

## Astra DB Connectivity

Astra connectivity milestone date/time:

- 2026-08-13 13:32:37 +06 +0600

Files added:

- scripts/check_astra.py
- tests/test_check_astra.py

Files updated:

- .gitignore
- docs/BUILD_STATE.md

AstraPy behavior used:

- Installed astrapy version: 2.3.1
- DataAPIClient imported from astrapy.
- Database object obtained with DataAPIClient(...).get_database(...).
- ASTRA_DB_KEYSPACE is passed only when configured; it is not forced when blank.
- Read-only inspection uses database.list_collection_names().

Smoke test result:

- .venv/bin/python scripts/check_astra.py: passed
- Accessible collections inspected: 0

Test result:

- .venv/bin/python -m pytest: 4 passed

Connectivity guardrails:

- Endpoint and token were not printed.
- No secrets recorded in BUILD_STATE.md.
- No inserts, updates, deletes, truncates, drops, or collection creation attempted.
- personal_data and notes collections were not created.
- No Langflow work performed.

## Structured Profile Collection

Structured profile collection milestone date/time:

- 2026-08-13 13:42:10 +06 +0600

Files added:

- scripts/setup_personal_collection.py
- tests/test_setup_personal_collection.py

AstraPy behavior used:

- Installed astrapy version: 2.3.1
- DataAPIClient imported from astrapy.
- Database object obtained with DataAPIClient(...).get_database(...).
- ASTRA_DB_KEYSPACE is passed only when configured; it is not forced when blank.
- Existing collections are inspected with database.list_collection_names() and database.list_collections().
- Missing profile collection is created with database.create_collection(collection_name) without a vector definition or rigid schema.

Collection result:

- Collection name: personal_data
- First setup run: created normal non-vector collection
- Second setup run: reused existing collection
- Visible collection count after setup: 1

Application-level profile document shape:

- _id: generated by Astra
- name
- age
- weight
- height
- gender
- activity_level
- goals: list
- nutrition: object with calories, protein, fat, carbs

Test result:

- .venv/bin/python -m pytest: 7 passed

Structured profile collection guardrails:

- Existing collection was never dropped, overwritten, or recreated.
- No example user data inserted.
- No inserts, updates, deletes, truncates, or drops performed.
- notes collection was not created.
- No Langflow work performed.
- Endpoint and token were not printed.
- No secrets recorded in BUILD_STATE.md.

## Notes Vectorize Collection

Notes collection milestone date/time:

- 2026-08-13 13:49:08 +06 +0600

Files added:

- scripts/setup_notes_collection.py
- tests/test_setup_notes_collection.py

AstraPy and Data API behavior used:

- Installed astrapy version: 2.3.1
- DataAPIClient imported from astrapy.
- Database object obtained with DataAPIClient(...).get_database(...).
- Supported embedding providers discovered with database.get_database_admin().find_embedding_providers().
- Collection metadata inspected with database.list_collection_names() and database.list_collections().
- ASTRA_DB_KEYSPACE is passed only when configured; it is not forced when blank.
- Existing notes collection is reused only when metadata shows the expected vectorize provider/model.
- Incompatible existing notes collection causes setup to stop because changing collection vector settings requires a migration or a new collection.

Selected vectorize configuration:

- Collection name: notes
- Provider: nvidia
- Model: nvidia/nv-embedqa-e5-v5
- Metric: cosine
- Visible provider/model dimension: 1024
- Vector dimension was not hardcoded in the collection definition.

Collection result:

- First setup run: created vectorize-enabled collection
- Second setup run: reused existing vectorize-enabled collection
- Final descriptor inspection: provider nvidia, model nvidia/nv-embedqa-e5-v5, metric cosine

Application-level note document shape:

- _id
- user_id
- text
- $vectorize containing the note text when required by current Data API writes
- generated $vector managed by Astra

Test result:

- .venv/bin/python -m pytest: 11 passed

Notes collection guardrails:

- No sample notes inserted.
- No manual $vector values inserted.
- No inserts, updates, deletes, truncates, or drops performed.
- Existing notes collection was never dropped, overwritten, or recreated.
- No fallback provider/model selected.
- Endpoint and token were not printed.
- No secrets recorded in BUILD_STATE.md.
- No Langflow work performed.

## Profile Database Operations

Profile database operations milestone date/time:

- 2026-08-13 13:55:09 +06 +0600

Files added:

- db.py
- tests/test_db.py

Public db.py API:

- get_database()
- get_personal_collection()
- list_profiles()
- get_profile(profile_id)
- create_profile(profile_data)
- update_personal_information(profile_id, updates)

Implementation notes:

- Uses config.py for ASTRA_DB_API_ENDPOINT, ASTRA_DB_APPLICATION_TOKEN, ASTRA_DB_KEYSPACE, and ASTRA_PERSONAL_COLLECTION.
- Uses installed astrapy DataAPIClient and current collection methods: get_collection, find, find_one, insert_one, update_one.
- ASTRA_DB_KEYSPACE is passed only when configured.
- Profile validation happens at the application boundary.
- _id is never accepted on create or update; Astra generates profile _id values.
- update_personal_information checks that the profile exists before update and uses upsert=False.
- No fake authentication system was created.
- No Streamlit UI was created.
- Notes operations were not implemented in db.py.

Test result:

- .venv/bin/python -m pytest: 29 passed

Profile operations guardrails:

- Unit tests use mocks and do not hit production Astra DB.
- No live profile documents inserted, updated, deleted, or queried by tests.
- No tokens or full database endpoint values printed.
- No secrets recorded in BUILD_STATE.md.

## Note Database Operations

Note database operations milestone date/time:

- 2026-08-13 14:03:02 +06 +0600

Files updated:

- db.py
- docs/BUILD_STATE.md

Files added:

- tests/test_db_notes.py
- scripts/smoke_notes.py

Public db.py note API:

- get_notes_collection()
- add_note(user_id, text)
- list_notes(user_id, limit=50)
- delete_note(user_id, note_id)
- update_note(user_id, note_id, text)

Implementation notes:

- Uses config.py for ASTRA_NOTES_COLLECTION.
- Every note write includes user_id.
- Readable note text is stored in text.
- Vectorize-enabled writes also send $vectorize with the same note text.
- No $vector value is manually generated or stored by the application.
- list_notes filters by user_id and limit.
- delete_note and update_note use filters containing both _id and user_id.
- update_note refreshes both text and $vectorize with upsert=False.
- Semantic search was not implemented in Python; RAG retrieval remains delegated to Langflow/Astra.

Manual smoke script:

- scripts/smoke_notes.py supports --user-id or SMOKE_PROFILE_ID.
- It requires --confirm-write-delete before inserting and deleting one clearly marked test note.
- Dry-run verification was executed without modifying data.

Test result:

- .venv/bin/python -m pytest: 41 passed
- .venv/bin/python scripts/smoke_notes.py --user-id dry-run-profile: dry run only, no data modified

Note operations guardrails:

- Unit tests use mocks and do not hit production Astra DB.
- No destructive smoke-test path was run.
- No sample notes inserted into live Astra DB during this milestone.
- No notes outside the explicitly supplied user_id can be deleted or updated through db.py helpers.
- No tokens or full database endpoint values printed.
- No secrets recorded in BUILD_STATE.md.

## Profile Domain Service Layer

Profile service layer milestone date/time:

- 2026-08-13 14:08:33 +06 +0600

Files added:

- profiles.py
- utils.py
- tests/test_profiles.py

Public profiles.py API:

- normalize_profile(profile)
- get_all_profiles()
- get_profile_by_id(profile_id)
- create_new_profile(...)
- save_profile_changes(profile_id, ...)
- build_profile_context(profile)

Implementation notes:

- profiles.py is a small domain/service layer over db.py.
- Profile documents are normalized into predictable dictionaries with stable field order.
- goals remain a list in storage.
- nutrition remains optional until macro generation.
- build_profile_context produces deterministic, human-readable text for Langflow prompt injection.
- The tutorial's exact dict_to_string helper was not present in this repository, so utils.py implements a local deterministic serializer as a project implementation choice, not copied tutorial code.
- No authentication system was created.
- No Streamlit UI was created.

Sanitized generated context example:

```text
Profile id: example-profile-id
Name: Example User
Age: 30
Weight: 70.5
Height: 175
Gender: unspecified
Activity level: moderate
Goals: build strength, improve endurance
Nutrition:
  Calories: 2200
  Protein: 150
  Fat: 70
  Carbs: 240
```

Test result:

- .venv/bin/python -m pytest: 50 passed

Profile service guardrails:

- Unit tests use mocks and do not hit production Astra DB.
- No live profile data inserted, updated, deleted, or queried.
- No tokens or full database endpoint values printed.
- No secrets recorded in BUILD_STATE.md.

## Langflow Macro Flow

Macro Flow milestone date/time:

- 2026-08-13 17:28:33 +06 +0600

Files added:

- docs/LANGFLOW_SETUP.md
- flows/macro_flow.json

Langflow runtime:

- Langflow URL used during manual build: http://127.0.0.1:7860
- Flow name: Macro Flow
- Flow ID: d0c80780-b504-471e-bc25-f203987baad3

Real exported component IDs:

- Profile runtime input: ChatInput-RkQmU
- Prompt Template: Prompt Template-VgARU
- OpenRouter model: ext:openrouter:OpenRouterComponent@official-snoVc
- Output: ChatOutput-mqlKE

Runtime contract observed:

- API version: v1
- Endpoint path: /api/v1/run/d0c80780-b504-471e-bc25-f203987baad3
- Auth header name: x-api-key
- input_type: chat
- output_type: chat
- Profile context strategy: normal chat input_value
- Goals strategy: Prompt Template tweak field goals on component Prompt Template-VgARU

Model configuration:

- Provider/component: OpenRouter
- Model selected from actual available OpenRouter list: openai/gpt-4o-mini
- Temperature: 0
- System instruction: return only valid JSON, no markdown or extra text

Playground verification:

- Three synthetic tests succeeded.
- Each output parsed as JSON with exactly calories, protein, fat, and carbs.
- All four values were numeric.

Export verification:

- flows/macro_flow.json exists and is non-empty.
- Export came from Langflow UI, not assistant-generated JSON.
- Save with my API keys was unchecked during export.
- Export inspection found no obvious OpenRouter or Astra secret strings.

Macro Flow guardrails:

- OpenRouter remains inside Langflow.
- No OpenRouter SDK was added to app requirements.
- ai.py and get_macros() were not implemented.
- Ask AI V2 was not created.
- No real secret was recorded in docs or exported flow.

## Macro Flow Manual Integration Script

Manual integration script milestone date/time:

- 2026-08-13 17:56:38 +06 +0600

Files added:

- scripts/test_macro_flow.py

Script behavior:

- Builds synthetic profile context through profiles.build_profile_context().
- Calls ai.get_macros().
- Prints a sanitized input summary, parsed nutrition dictionary, and request duration.
- Does not print API keys, tokens, raw headers, or full endpoint secrets.
- Does not save anything to Astra DB.
- Exits nonzero for Langflow call failure, parser failure, or missing nutrition fields.
- If parsing fails, performs one raw diagnostic Macro Flow call and prints a sanitized output preview, instructing the user to fix the Langflow prompt rather than weakening the parser.

Verification:

- .venv/bin/python -m pytest: 69 passed
- .venv/bin/python scripts/test_macro_flow.py: failed before reaching Langflow response parsing because Langflow was not reachable at 127.0.0.1:7860.
- 2026-08-13 18:00:22 +06 +0600 rerun: Langflow was reachable, but the request failed with HTTP 403 Forbidden.
- 2026-08-13 18:04:46 +06 +0600 rerun: passed with synthetic profile data; parsed nutrition dictionary contained calories, protein, fat, and carbs.

Sanitized failure:

- Error type: ConnectionError
- Reason: connection refused to local Langflow server at 127.0.0.1:7860
- Rerun error type: HTTPError
- Rerun reason: 403 Forbidden from local Langflow API; required Langflow environment variables were present but the API key was not accepted for this request.

Sanitized success:

- Parsed nutrition dict shape: calories, protein, fat, carbs
- Request duration: 2.94s

Manual integration script guardrails:

- Synthetic input only.
- No Astra DB write attempted.
- No Streamlit UI built.
- No secrets recorded in BUILD_STATE.md.

## Ask AI V2 Langflow Export

Ask AI V2 export validation date/time:

- 2026-08-13 22:13:00 +06 +0600

Files added:

- flows/ask_ai_v2.json

Files updated:

- docs/LANGFLOW_SETUP.md
- docs/BUILD_STATE.md

Langflow runtime:

- Langflow URL used during validation: http://127.0.0.1:7860
- Flow name: Ask AI V2
- Flow ID: b9b1438d-2ab4-461a-b86d-8f8806ddd5ad

Runtime contract observed:

- API version: v1
- Endpoint path: /api/v1/run/b9b1438d-2ab4-461a-b86d-8f8806ddd5ad
- Auth header name: x-api-key
- input_type: chat
- output_type: chat
- Response text path observed: outputs[0].outputs[0].results.message.data.text

Real exported runtime component IDs:

- Question input: ChatInput-sk4My
- Profile context tweak: Prompt Template-GtOCM.profile
- User ID filter tweak: ext:datastax:AstraDBVectorStoreComponent@official-2VBhC.advanced_search_filter

Topology validation:

- Router prompt, OpenRouter router model, and Conditional Router are present.
- Math path contains one Agent and one Calculator tool.
- Advice path contains Astra DB vector search, Parser, advice Prompt Template, OpenRouter model, and advice Chat Output.
- This is one tool-calling Agent plus one normal RAG chain, not multiple peer agents.

Privacy configuration:

- Astra collection: notes
- Content field: text
- Search metadata filter includes user_id.
- Runtime filter value must be supplied from the selected profile ID; no real user ID is hardcoded.

Verification:

- Live synthetic math API call: passed.
- Export secret scan: no obvious OpenRouter API key or Astra token strings found.
- Full User A/User B retrieval isolation proof: passed on 2026-08-13.
- Synthetic User A retrieved only the User A test note.
- Synthetic User B retrieved only the User B test note.
- A nonexistent synthetic user retrieved neither private test note.
- The test inserted two synthetic notes through db.add_note and deleted those same notes after verification.

Ask AI V2 guardrails:

- Flow JSON came from Langflow export.
- No assistant-generated flow JSON was created.
- OpenRouter remains inside Langflow.
- No ai.py Ask AI V2 integration was implemented.
- No secrets recorded in BUILD_STATE.md.

## Compatibility Audit

Audit date/time:

- 2026-08-14 01:06:32 +0600 +06

Known working environment:

- Python executable: `.venv/bin/python`
- Python version: 3.11.15
- Platform: macOS-26.6.1-arm64-arm-64bit
- CPU architecture: arm64
- Langflow export tested version: 1.11.3

Direct package versions pinned for reproducibility:

- streamlit==1.61.1
- astrapy==2.3.1
- python-dotenv==1.2.2
- requests==2.34.2
- pytest==9.1.1

Compatibility decisions:

- `requirements.txt` pins only the direct application dependencies currently used by the app.
- `requirements-dev.txt` pins only the direct development dependency currently used for tests.
- Transitive dependencies are intentionally not listed manually.
- The installed Streamlit exposes `st.fragment`, but `main.py` does not depend on it.
- The Langflow run API uses `/api/v1/run/<flow_id>` and `x-api-key`, not tutorial-era Bearer auth.
- Astra notes use server-side vectorize with provider `nvidia`, model `nvidia/nv-embedqa-e5-v5`, dimension `1024`, metric `cosine`.
- Python note inserts send text through `$vectorize`; Python never creates guessed `$vector` values.

Validation results:

- `pip check`: PASS, no broken requirements found.
- `pytest -q`: PASS, 109 tests passed.
- `python -m compileall -q -x '(^|/)(\\.venv|__pycache__)(/|$)' .`: PASS.
- Non-destructive Astra smoke: PASS, accessible collections inspected: `notes`, `personal_data`.
- Non-destructive Astra vectorize smoke: PASS, `notes` provider/model is `nvidia` / `nvidia/nv-embedqa-e5-v5`.
- Non-destructive Macro Flow smoke: PASS, response parsed into `calories`, `protein`, `fat`, `carbs`.
- Non-destructive Ask AI math smoke: PASS, answer contained the expected arithmetic result `108`.

## Final Local Use Preparation

Date/time:

- 2026-08-14 01:18:31 +0600 +06

Status:

- COMPLETE

Files updated:

- README.md
- docs/BUILD_STATE.md

Verification commands:

- `.venv/bin/python -m pip check`: PASS, no broken requirements found.
- `.venv/bin/python scripts/check_config.py --mode all`: PASS, required environment variable names are set; values redacted.
- `.venv/bin/python -m pytest -q`: PASS, 109 tests passed.
- `.venv/bin/python -m compileall -q -x '(^|/)(\\.venv|__pycache__)(/|$)' .`: PASS.
- `.venv/bin/python scripts/check_astra.py`: PASS, read-only connectivity check inspected `notes` and `personal_data`.
- `.venv/bin/python scripts/test_macro_flow.py`: PASS, parsed nutrition dict with `calories`, `protein`, `fat`, `carbs`.
- `.venv/bin/python scripts/live_acceptance.py`: PASS for Astra, Macro Flow, Ask AI math, Ask AI RAG, cross-profile isolation, and cleanup.
- `.venv/bin/python -m streamlit run main.py --server.headless true --server.port 8502`: PASS, app started without immediate exception; verification server stopped.

Known limitations:

- This app provides profile separation, not real multi-user authentication.
- Fitness output is general guidance, not medical diagnosis or clinical nutrition advice.
- Public deployment requires a reachable hosted Langflow service; a local `127.0.0.1` Langflow URL is only valid for local development.
- OpenRouter remains inside Langflow; Streamlit does not call OpenRouter directly.

## AUTH-01 Account Storage Foundation

Date/time:

- 2026-08-26 20:07:06 +0600

Status:

- PASS

Results:

- `ASTRA_ACCOUNTS_COLLECTION` is configured with default `accounts`.
- `argon2-cffi` is present as an application dependency and importable; planned password hashes use Argon2id.
- `scripts/setup_accounts_collection.py` created the `accounts` collection on the first live run.
- A second live run safely reused the existing `accounts` collection.
- No account documents, example passwords, or password hashes were inserted.
- Existing profile, note, Langflow, Ask AI, and Streamlit behavior was not changed in this milestone.

Verification commands:

- `.venv/bin/python -m pytest -q`: PASS, 115 tests passed.
- `.venv/bin/python -m compileall -q -x '^\\./\\.venv(/|$)' .`: PASS.
- `.venv/bin/python -m pip check`: PASS, no broken requirements found.
- `rg '^argon2-cffi' requirements.txt && .venv/bin/python -c 'import argon2; print("argon2 import ok")'`: PASS.
- `.venv/bin/python scripts/setup_accounts_collection.py`: PASS, action `created`.
- `.venv/bin/python scripts/setup_accounts_collection.py`: PASS, action `reused`.

Next milestone:

- AUTH-02 registration/authentication logic.
