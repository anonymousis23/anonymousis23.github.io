# PHONOS voice-similarity ABX study

This study contains 60 randomized trials: 20 each from PHONOS, SeedVC, and
TVTSyn. Participants hear reference A, reference B, and converted sample X,
then select which reference voice is closer to X and report confidence from 1
to 7.

## Study design

- Five trials are shown per page.
- A 12-second listening break appears after every 15 completed trials.
- Source and converted samples are between 4 and 8 seconds.
- The expected answer is balanced: A for 30 trials and B for 30 trials.
- A/B source and target placement is hidden from the participant.
- SeedVC and PHONOS are expected to match the target speaker.
- TVTSyn is a reconstruction model and is expected to match the source speaker;
  its target-accent reference is an unconditioned distractor.

PHONOS samples are manually accepted conversions that pass target AccentCL
recall, NISQA-MOS >= 4.0, and target-speaker cosine similarity >= 0.84. SeedVC
and TVTSyn are reproducibly sampled after duration filtering.

## Before launch

Set `prolific_completion_url` in `trials.json`. The response endpoint is shared
with the other PHONOS-TASLP26 studies and is currently configured as:

`https://juggle-rematch-marry.ngrok-free.dev/api/submissions`

Prolific parameters `PROLIFIC_PID`, `STUDY_ID`, and `SESSION_ID` are captured
from the study URL. The internal study ID is
`phonos_taslp26_voice_similarity_abx`.

## Data files

- `trials.json`: web configuration and fixed randomized order.
- `trials.csv`: public trial metadata and A/B ground truth.
- `selection/voice_similarity_selection.csv`: complete local-path audit trail.
- `selection/selection_summary.json`: sampling criteria and counts.
- `selection/phonos_similarity_candidates.csv`: PHONOS quality/similarity pool.

Regenerate the study with:

```bash
/data/waris/installations/darkstream/bin/python \
  UserStudy/PHONOS-TASLP26/scripts/prepare_voice_similarity_abx.py
```
