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
