# Content guidelines

The content library in `content/` is the source of truth for every non-emergency answer NURU sends. The LLM may rephrase it; it may not add to it.

## Entry format

```yaml
- id: preg_myth_eggs                  # unique, prefix by life stage
  topic: lishe_ujauzito
  life_stage: pregnancy               # adolescence | preconception | pregnancy | postpartum | newborn | under5
  type: myth                          # faq | myth
  questions:                          # how real users ask it: Kiswahili first, SMS spelling welcome
    - ni kweli mjamzito asile mayai
    - is it true pregnant women should not eat eggs
  keywords: [mayai, mwiko, mjamzito]
  answer_sw: >-                       # what is sent; GSM-7, at most 306 characters
    Si kweli. Mama mjamzito anaweza ...
  note_en: >-                         # English summary for reviewers and translators
    Myth: ... Fact: ...
  sources:
    - WHO recommendations on antenatal care for a positive pregnancy experience (2016)
  status: draft_pending_clinical_review   # or clinically_approved, retired
  reviewed_by: null                       # name and date of the approving clinician
```

## Writing rules

1. **Kiswahili first**, simple and warm, for a reader with primary education. Avoid medical jargon; if a term is needed, use the common word (hedhi, kliniki, chanjo).
2. **At most 306 characters** (2 SMS), GSM-7 only: no smart quotes, no emoji. The test suite rejects entries that do not fit.
3. **One idea per entry.** Answer the question, give one or two actions, say when to go to a facility.
4. **Conservative and consistent with WHO and Tanzania MoH guidance.** When evidence or national policy is unclear, say "muone mtaalamu wa afya" (see a health worker).
5. **Never diagnose.** Describe signs in general ("dalili za ... ni kama ..."), never "you have ...".
6. **No doses** except where national guidance gives a single universal instruction; otherwise "kama maelekezo ya pakiti" or "kama kliniki itakavyoshauri".
7. **Myths**: open with "Si kweli." then the fact, then a reassuring action. Do not repeat the myth in a way that reinforces it.
8. **Discreet**: write so the message is not embarrassing if someone else reads the phone. No names, no "your result".
9. **Danger signs** belong in the red-flag engine, not only in content. An entry may describe danger signs in general, but a user reporting one is caught earlier by `red_flags.py`.
10. **Questions list**: add at least three real phrasings, including common SMS spellings and one English variant. Retrieval quality depends on this more than on the answer text.

## Clinical review workflow

| Step | Who | Output |
|---|---|---|
| 1. Draft | Content writer or clinician | Entry with `status: draft_pending_clinical_review`, sources listed |
| 2. Language check | Native Kiswahili speaker from the target community | Plain-language edits; read aloud test with 3 to 5 adolescents or mothers |
| 3. Clinical review | Licensed medical doctor or senior midwife, not the author | Accuracy against WHO and MoH sources; check it refers when appropriate |
| 4. Approve | Clinical lead | `status: clinically_approved`, `reviewed_by: "<name>, <YYYY-MM-DD>"` |
| 5. Publish | Engineer | Merged via pull request; tests must pass |
| 6. Audit | Clinician panel, monthly | Random sample of real answers rated correct / incorrect / unsafe; feeds the "% answers rated correct" pilot metric |

Rules:

- A pull request that changes `answer_sw`, a red-flag pattern or a fixed message needs approval from a clinician reviewer in addition to code review.
- Content is reviewed at least every 12 months, or immediately when WHO or MoH guidance changes.
- In production, the service should load only `clinically_approved` entries. The prototype loads drafts so the demo works; every entry is visibly marked draft.

## Sources to cite

- WHO recommendations on antenatal care for a positive pregnancy experience (2016)
- WHO recommendations on maternal and newborn care for a positive postnatal experience (2022)
- WHO Family Planning: A Global Handbook for Providers (2022)
- WHO Guidelines for the management of symptomatic sexually transmitted infections (2021)
- WHO / UNICEF Integrated Management of Childhood Illness (IMCI)
- Tanzania Ministry of Health national guidelines (antenatal care, family planning, immunisation, adolescent and youth friendly services)

Always cite the specific national guideline and edition used during review in the `sources` field.
