# Google Form setup

The generated Apps Script creates four blinded form variants, a private administrator spreadsheet,
individual response sheets, and participant-to-form assignments for `P001` through `P040`.
Each participant evaluates 12 cases from the balanced 24-case pool. Response A/B order and case
sets are counterbalanced across variants.

## Create the forms

1. Open [Google Apps Script](https://script.google.com/) while signed into the account that should
   own the study data.
2. Select **New project** and name it `ResolveAI Human Feedback`.
3. Delete the example function in `Code.gs`.
4. Copy the entire contents of `create-resolveai-google-forms.gs` into `Code.gs`.
5. Save, select `createResolveAIForms`, and click **Run**.
6. Approve the Google Forms and Google Sheets permissions. The script only creates resources in
   the signed-in account.
7. Open **Execution log**. It prints the administrator spreadsheet and four form links.
8. In the administrator spreadsheet, open `PARTICIPANT-ALLOCATION`. Send each participant only
   the URL in their assigned row.

Do not share the `ADMIN-CONTROL` sheet because it contains the A/B blinding key. The generated
forms collect full name and Google-account email and limit each account to one response. Obtain
faculty or institutional approval before sending the forms to participants.

## Study operation

- Recruit 40 people to target at least 36 completed responses.
- Give each participant a pseudonymous ID from `P001` to `P040`.
- Tell participants that full name and email are recorded for attendance and duplicate control.
- Ask participants not to enter phone numbers or real customer data.
- Close all four forms at the same time.
- Make an access-restricted copy containing the identity columns.
- Before analysis, create a de-identified CSV that removes name, email, and Google-account fields.
- Export each de-identified response sheet as CSV before joining it to the blinding key.
- Preserve incomplete and unfavorable responses in the analysis log.

Regenerate the script after benchmark changes with:

```powershell
.\.venv\Scripts\python.exe scripts\build_google_form_script.py
```
