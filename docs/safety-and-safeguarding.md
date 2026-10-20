# Safety and safeguarding

NURU is health **education**. It does not diagnose, prescribe or replace a health worker. Its most important job is to send people to care quickly when it matters.

## 1. Red-flag engine (runs first, always)

Every inbound message is screened before anything else, including when the user is in the middle of a facility-finder exchange. If a rule matches:

- NURU sends a **fixed message** written by a clinician (`nuru/red_flags.py`, `FIXED_MESSAGES`);
- processing stops: no retrieval, **no LLM call**;
- the reply is logged with category `red_flag` or `safeguarding` and the rule id, for audit and (phase 2) CHW or nurse call-back.

Tests in `tests/test_red_flags.py` assert that a provider which raises on any call is never reached for a danger-sign message, and that an "overconfident" provider cannot override a red flag.

### Rules in the prototype

| Rule | Examples (Kiswahili / English) | Message |
|---|---|---|
| Self-harm | kujiua, nataka kufa / kill myself | `SAFEGUARDING_SELF_HARM` |
| Convulsions, loss of consciousness | degedege, amezimia / seizure, fainted | child, maternal or general by context |
| Breathing difficulty | anapumua kwa shida / difficulty breathing | child, maternal or general by context |
| Bleeding in pregnancy or after birth | nina mimba natoka damu / pregnant and bleeding | `URGENT_MATERNAL` |
| Headache with blurred vision | kichwa kinauma, naona ukungu | `URGENT_MATERNAL` |
| Severe headache, face or hand swelling, fever, severe abdominal pain in pregnancy | | `URGENT_MATERNAL` |
| Waters breaking | maji yamevunjika, chupa imepasuka | `URGENT_MATERNAL` |
| Reduced fetal movement | mtoto tumboni hachezi | `URGENT_MATERNAL` |
| Baby not breastfeeding or child unable to drink | hanyonyi, hawezi kunywa | `URGENT_CHILD` |
| Child vomits everything, lethargic | anatapika kila kitu, amelegea | `URGENT_CHILD` |
| Fever or cold body in a newborn | mtoto mchanga ana homa | `URGENT_CHILD` |
| Newborn jaundice | mtoto mchanga ana manjano machoni | `URGENT_CHILD` |
| GBV and abuse disclosure | nimebakwa, mume wangu ananipiga / raped | `SAFEGUARDING_GBV` |

The child rules follow the IMCI general danger signs; the maternal rules follow WHO and Tanzania MoH pregnancy danger signs.

### Design principles

- **Broad on purpose.** "Je, ni kawaida kutoka damu nikiwa mjamzito?" is escalated even though it is phrased as a question. A false positive costs one SMS. A false negative can cost a life.
- **Fixed text only.** Messages are short, imperative, name no condition, and always end with how to find the nearest facility (`KITUO` + ward).
- **No echo.** Messages never repeat what the user wrote.
- **Clinicians own the rules.** Changing a pattern or message requires clinical sign-off (see content guidelines). Every message carries `review_status`.

### Known limits of the prototype

- Keyword rules miss unusual spellings and indirect phrasing. The pilot will add a weekly clinician review of a random sample of non-flagged messages to find misses and add patterns.
- Negation ("sitoki damu", "I am not bleeding") is not handled; such messages are escalated. This is accepted.
- English rules exist for code-switching; replies are in Kiswahili.

## 2. AI guard-rails

- The LLM receives only the question (phone-number-like digit runs redacted) and the top retrieved passages. It never receives the phone number, history or location.
- The system prompt requires: answer only from the passages, simple Kiswahili, at most 306 characters, no diagnosis, no doses not in the passages, refer to a facility when the passages do not answer.
- If retrieval confidence is below `NURU_MIN_RETRIEVAL_SCORE`, the LLM is not called; NURU sends a safe fallback that advises a facility visit.
- Any provider error, timeout or empty output returns the library answer.
- `NURU_LLM_PROVIDER=none` removes generative AI entirely while keeping the service useful.

## 3. Privacy on shared phones

Many girls share a phone with a parent, sibling or partner. NURU therefore:

- uses a **neutral sender** (shortcode or a neutral sender ID, never a name that reveals the topic);
- keeps wording **discreet**: no reply repeats the question, and no message says "your pregnancy test" or similar;
- does **not echo sensitive history**: there is no "last time you asked about..." feature;
- **asks** for location (ward or village) only when the user wants a facility, and does not store it;
- logs only a salted hash of the phone number, a category and content ids; message text is not logged;
- supports `STOP` at any time.

In the pilot, the opt-in message will remind users that SMS can be read by others with access to the phone and how to delete messages.

## 4. Safeguarding minors and GBV disclosures

- **GBV**: the fixed reply says it is not their fault, urges a facility visit as soon as possible and ideally within 72 hours (post-exposure prophylaxis for HIV and emergency contraception), says to go now if hurt, gives the free helpline **116**, and advises going somewhere safe.
- **Self-harm**: the reply urges telling a trusted person now, going to a facility, and gives 116 for under-18s.
- NURU cannot verify age and does not ask for it in the prototype. All content is written to be appropriate for adolescents.
- **Pilot protocol (phase 2)**: safeguarding categories trigger an alert to a trained, named safeguarding focal person who follows the national referral pathway (Police Gender and Children Desks, social welfare officers, One Stop Centres where available). Mandatory reporting obligations for minors will be confirmed with the Ministry and UNICEF before launch.
- The helpline number and referral pathway must be re-verified with the Ministry and UNICEF Tanzania before any public launch.

## 5. Facility data

- The prototype ships a small **sample** CSV with placeholder names. Every facility reply in sample mode ends with "[Data ya mfano, si rasmi]".
- Before the pilot, the file must be replaced with the official MoH Health Facility Registry (HFR) export. Only government facilities are returned.

## 6. Incident handling

Any report of harmful or wrong advice is treated as a clinical incident: the content entry or rule is disabled within 24 hours, reviewed by the clinical lead, corrected, re-reviewed and re-enabled, with the change recorded in the content changelog.
