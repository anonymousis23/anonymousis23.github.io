# Multidimensional accent-perception study

This directory contains the matched audio set and participant interface for the revised accent study. There are 10 source groups for each of six conversion directions. Each group contains:

- the original source utterance;
- the manually shortlisted PHONOS conversion;
- a SeedVC conversion of the identical source utterance, using its target reference from the objective evaluation; and
- the TVTSyn reconstruction of the identical source utterance.

selection_manifest.csv is the wide provenance and objective-score audit. stimuli_manifest.csv is the long-form list of 240 audio stimuli. JSON equivalents and fixed seeds are included for reproducibility.

## Study forms

The participant interface is index.html. forms.json contains four counterbalanced forms, each with 60 trials:

- 15 Original, 15 PHONOS, 15 SeedVC, and 15 TVTSyn samples;
- 10 samples from each of the six conversion directions;
- one condition per source-direction group; and
- no repeated Original or TVTSyn recording within a form.

Across forms A-D, each source-direction group is presented once in every condition. Repeated linguistic sources are separated by at least 15 trials within a form. Append ?FORM_ID=A, B, C, or D to load a specific form. When FORM_ID is absent or invalid, the landing page asks the visitor to select one of the four forms and then reloads the study with that identifier while preserving any Prolific URL parameters. With 80 usable participants, allocate 20 participants to each form.

Before launch, set prolific_completion_url in forms.json. The internal study ID is phonos_taslp26_accent_multidimensional.

## Regeneration

Run from the repository root:

    /data/waris/installations/darkstream/bin/python UserStudy/PHONOS-TASLP26/scripts/prepare_accent_new_samples.py
    /data/waris/installations/darkstream/bin/python UserStudy/PHONOS-TASLP26/scripts/build_accent_new_study.py
