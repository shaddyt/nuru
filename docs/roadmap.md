# Roadmap

## Phase 1: prototype and demo (current)

Goal: show the full SMS loop working safely end to end.

- [x] Two-way SMS webhook for Africa's Talking (sandbox) and RapidPro
- [x] Red-flag and safeguarding engine with fixed messages, checked before AI
- [x] Retrieval over a Kiswahili content library (25 draft entries)
- [x] Swappable LLM provider (OpenAI, Anthropic Claude, Google Gemini) with offline mode
- [x] Myth library (periods, contraception, HIV, pregnancy nutrition, colostrum)
- [x] Facility finder by ward or village (sample data)
- [x] GSM-7, 2-SMS reply limit
- [x] CLI simulator and automated tests
- [ ] Clinical sign-off of all content entries and fixed messages
- [ ] Official MoH HFR export loaded
- [ ] Toll-free shortcode agreement with mobile network operators via Africa's Talking

## Phase 2: Dodoma pilot (2027)

Goal: real users in Dodoma Region, measured against the pilot metrics.

- Life-stage scheduled tips (opt-in): weekly pregnancy messages by gestational week, postpartum and newborn messages, adolescent series. Built as RapidPro flows.
- CHW and nurse call-back escalation: red-flag and safeguarding events create a call-back task for a trained health worker, with consent.
- Under-five module: danger signs, lishe (nutrition, complementary feeding), immunisation reminders and follow-up.
- Anonymised MoH insight dashboard: question topics, myth prevalence, red-flag volume by council, with no personal data.
- Content library expanded to several hundred clinically approved entries.
- Production hosting, monitoring, Redis session store, data-processing agreements.

### Pilot metrics

| Metric | How it is measured |
|---|---|
| Unique users and questions per month | Hashed user ids and inbound counts |
| % answers rated correct by clinician audit | Monthly random sample, rated by a clinician panel |
| % red flags correctly escalated | Audit sample of all messages: true danger signs that received the fixed message |
| % reporting a facility visit after referral | Follow-up SMS 48 to 72 hours after a red flag or facility lookup (opt-in) |
| Cost per active user | SMS, hosting and LLM cost divided by monthly active users; target under US$1 |

## Phase 3: scale

- Kiswahili voice line (IVR) for users who cannot read, and USSD menus.
- More languages and channels, including WhatsApp for smartphone users.
- Adaptation for other UNICEF programme countries: content localisation, local facility registries, local safeguarding pathways.
- Open content packs so ministries and NGOs can reuse the reviewed library.
