# Deployment Readiness

Review date: 2026-08-20

Final classification: SAFE FOR PRIVATE SINGLE-USER HOSTING WITH CONDITIONS

This is a deployment-readiness review only. No deployment infrastructure was created.

## Architecture Boundary

The current app is a Python and Streamlit tutorial application. It uses Astra DB profile documents and note documents, and Langflow handles AI orchestration through Macro Flow and Ask AI V2.

Important security boundary:

- The app separates data by profile document ID and `user_id` filters.
- The app does not implement real user authentication.
- The app does not implement per-user authorization.
- A selected profile ID must not be treated as proof of ownership in a public multi-user deployment.

## Safe Deployment Scenarios

| Scenario | Readiness | Conditions |
| --- | --- | --- |
| Private/local-only | Safe | Run Streamlit and Langflow on a trusted local machine. Keep `.env` local. Do not expose the app or Langflow to untrusted users. |
| Single-user private cloud | Safe with conditions | Restrict access with a private network, VPN, IP allowlist, platform-level access control, or another trusted outer gate. Use HTTPS for non-local service URLs. Store secrets only as server-side environment variables. |
| Public multi-user | Not ready | Requires an authentication and authorization redesign before deployment. |

## Public Multi-User Gaps

Public multi-user deployment is not recommended until these are implemented:

- Authentication: users must sign in with a trusted identity provider.
- Per-user authorization: every profile and note operation must verify ownership server-side.
- Secure session/user mapping: the app must map the authenticated session to a server-side user ID, not a user-selected profile ID.
- Ownership enforcement: profile reads, profile updates, note reads, note writes, note deletes, Macro Flow calls, and Ask AI calls must all be scoped to the authenticated owner.
- UI restriction: users must not be able to list or select all profiles in the database.
- Audit/rate limits: public deployment should include abuse controls and operational logging without secrets.

## Environment Variables

Use the variable names from `.env.example` on the hosting platform. Do not upload `.env`.

Required server-side values include:

- `ASTRA_DB_API_ENDPOINT`
- `ASTRA_DB_APPLICATION_TOKEN`
- `ASTRA_DB_KEYSPACE` if required by the current Astra setup
- `ASTRA_PERSONAL_COLLECTION`
- `ASTRA_NOTES_COLLECTION`
- `LANGFLOW_URL`
- `LANGFLOW_API_KEY`
- `MACRO_FLOW_ID`
- `ASK_AI_FLOW_ID`
- `MACRO_PROFILE_COMPONENT_ID`
- `MACRO_GOALS_COMPONENT_ID`
- `ASK_PROFILE_COMPONENT_ID`
- `ASK_USER_ID_COMPONENT_ID`

OpenRouter credentials should remain configured inside Langflow for this architecture. Do not move OpenRouter secrets into browser/client-side code.

## Network Access

The hosted Streamlit app must be able to reach:

- Astra DB over HTTPS.
- Langflow over a reachable server URL.

The hosted Langflow instance must be able to reach:

- OpenRouter.
- Astra DB for Ask AI V2 retrieval.

`LANGFLOW_URL=http://127.0.0.1:7860` only works when Streamlit and Langflow run on the same machine/process environment. In cloud hosting, `127.0.0.1` means the cloud server itself, not the developer laptop. Use a hosted Langflow URL or a private network address reachable from the Streamlit host.

The current `ai.py` client allows plain HTTP only for localhost-style URLs. Non-local Langflow URLs must use HTTPS.

## Streamlit Hosting Notes

Streamlit is a Python server application, not a static frontend. It needs a host that can run a long-lived Python process or container.

`st.session_state` is useful for browser-session UI state, but it is not an authentication boundary. Do not use session state alone to decide data ownership in a public deployment.

The app stores durable application data in Astra DB, which is appropriate for cloud hosting. Do not rely on local files for user data after deployment.

## Recommended Deployment Posture

For this project as currently built:

1. Local use is safe for a trusted developer machine.
2. Private single-user hosting is acceptable if protected by an outer access control layer and HTTPS.
3. Public multi-user hosting is not ready.

## Pre-Hosting Checklist

- Import the real Langflow flows into the Langflow environment that the hosted app will call.
- Set server-side environment variables from `.env.example`.
- Keep `.env` and `.env.local` out of source control.
- Verify `LANGFLOW_URL` is reachable from the Streamlit host.
- Verify Langflow API access uses the documented `x-api-key` header.
- Run the config checker.
- Run the Astra read-only smoke check.
- Run Macro Flow and Ask AI integration tests.
- Confirm no real secrets are committed.

