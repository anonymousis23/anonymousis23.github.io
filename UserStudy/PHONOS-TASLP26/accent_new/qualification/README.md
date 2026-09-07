# Accent qualification

This page presents 12 natural English recordings on one page. Participants must play every recording and identify its primary accent as American, British, Indian, or Spanish. The response API stores and scores the attempt; a perfect score continues to the assigned main-study form.

The public trials.json intentionally contains no expected labels. The private answer key is stored outside this directory and must be configured as the server QUALIFICATION_ANSWER_KEY environment variable.

Before launch, set each `A`-`D` entry in `screenout_completion_urls` in `trials.json` to that form's dedicated Prolific screened-out completion URL. A passing participant returns to the same `FORM_ID` they entered with.
