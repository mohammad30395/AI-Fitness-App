# Acceptance Tests

## Profile UI

- Create a profile with name, age, weight, height, gender, activity level, and at least one goal.
- Select the created profile from the existing profile selector.
- Edit one field on the selected profile and save the change.
- Refresh the browser, then reselect the profile and confirm the saved change is still present.

## Nutrition / Macros UI

- Select a non-sensitive sample profile with at least one goal.
- Confirm the Nutrition / Macros section shows existing saved targets, or a clear empty state.
- Click Generate with AI and confirm suggested calories, protein, fat, and carbs populate the editable fields.
- Change one suggested value manually, then click Save / Apply nutrition.
- Refresh the browser, reselect the same profile, and confirm the saved nutrition values persist.
- Confirm an AI/API/parser failure shows an on-page error without crashing the app.

## Notes UI

- Select or create profile A and add a unique synthetic note.
- Select or create profile B and confirm profile A's unique note is not visible.
- Add a different unique synthetic note to profile B.
- Switch back to profile A and confirm profile A's note is still visible.
- Delete profile A's note using the confirmation step and confirm profile B's notes are unchanged.

## Ask AI UI

- Select a profile and ask a calculator-style question, such as calories remaining after meals, and confirm the answer comes back without a page crash.
- Add a unique synthetic note to profile A, then ask a general fitness question that should reference that note.
- Switch to profile B and ask a similar note-based question; confirm profile A's unique note is not referenced.
- Switch back to profile A and confirm Ask AI can still use profile A's own note context.
- Ask a blank question and confirm the UI shows a clear validation error.
- Ask about injury, severe pain, neurological symptoms, chest pain, or another concerning health issue and confirm the answer avoids diagnosis and recommends appropriate professional care.
