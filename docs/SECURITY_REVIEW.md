# Security Review

Audit date: 2026-08-14 00:42:41 +06

Scope: local repository, tracked files, exported Langflow flows, Python application code, direct dependencies, and sanitized git-history secret scan.

## Summary

Result: PASS with deployment limitations.

The current application is acceptable for the staged tutorial architecture: Python/Streamlit calls Langflow and Astra, OpenRouter stays inside Langflow, Astra stores profile data and vectorized notes, and `.env` remains local-only. This is profile separation, not real user authentication.

## Secrets

- `.env` and `.env.local` are ignored by Git.
- `.env.example` contains placeholders only.
- Current tracked files were scanned for exact local secret values and common Astra/OpenRouter key patterns; no real secret findings were detected.
- Git history was scanned for exact local secret values and common Astra/OpenRouter key patterns; no real secret findings were detected.
- The first broad scan flagged synthetic test tokens in unit tests and `ASTRA_DB_KEYSPACE` metadata in `flows/ask_ai_v2.json`; these are not credentials.
- Langflow/OpenRouter credentials are expected to stay server-side in Langflow or deployment environment variables. Do not export Langflow flows with saved API keys.

If a real credential is ever committed in the future, deleting the file is not enough. Rotate the credential in the provider portal.

## Data Isolation

- Note writes include `user_id`.
- Note listing is scoped by `user_id`.
- Note deletion and update require both `_id` and `user_id`.
- Ask AI V2 runtime tweaks pass a `user_id`-based Astra filter to the Langflow Astra component.
- Privacy-isolation tests previously confirmed User A and User B note isolation.

Limitation: profile IDs are not authentication. For any internet deployment, add real authentication and server-side authorization before trusting a submitted profile ID.

## HTTP

- Langflow requests use finite timeouts and call `raise_for_status()`.
- Langflow HTTP errors, timeouts, connection failures, and response shape changes are converted to custom application errors without printing secrets.
- Remote Langflow URLs must use HTTPS; local `http://127.0.0.1`, `localhost`, and `::1` remain allowed for development.
- Astra Data API endpoint validation requires HTTPS.

## Inputs

- Blank notes and questions are rejected.
- Profile create/update rejects `_id`, unsupported fields, invalid numeric values, blank required string fields, and blank goal entries.
- Nutrition parsing uses `json.loads`, never `eval`.
- Macro parsing accepts plain JSON or a JSON object in a Markdown code fence, then requires exactly `calories`, `protein`, `fat`, and `carbs`.
- Streamlit does not render raw model HTML with `unsafe_allow_html`.

## Fitness Boundary

- UI copy frames output as general fitness guidance, not medical advice.
- Ask AI prompts include a boundary for injury, significant pain, alarming symptoms, and medical concerns.
- Macro targets are treated as approximate planning values, not clinical prescriptions.

## Dependencies

Direct runtime dependencies remain intentionally small:

- `streamlit`
- `astrapy`
- `python-dotenv`
- `requests`

Direct dev dependency:

- `pytest`

`pip check` result: no broken requirements found.

## Verification

- `python -m pytest -q`: 109 passed.
- `python -m compileall -q -x './.venv/.*' .`: passed.
- Secret scan: current tracked files and git history scanned with sanitized output; no real secret findings detected.

## Remaining Limitations

- This is still a tutorial app with profile separation only, not multi-user authentication.
- Langflow itself must be hosted securely for deployment; local `127.0.0.1` URLs cannot serve a public Vercel deployment.
- Exported Langflow JSON can contain provider/component configuration metadata. Review every export before committing, and leave `Save with my API keys` unchecked.
- Live provider-side IAM, Astra database access roles, Vercel project settings, and Langflow Cloud settings were not audited beyond the local configuration contract.
