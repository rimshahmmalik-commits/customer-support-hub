# Delivery verification

Build verification: 10 November 2026. All data is synthetic.

## Automated checks

**54 tests passed** using `python -m unittest discover -s tests -v`. They cover refund routing, negation, safety overrides, ambiguous complaints, structured output validation, invented quote rejection, mocked API responses, incomplete responses, persistent review decisions, stale edits, safety downgrade protection, empty reports, date windows, evidence references, HTTP input validation, origin checks, private file boundaries, explicit fallback and CSV formula escaping.

New checks cover dashboard ageing and priority calculations, empty/training views, image validation and case binding, mocked image transcription, transcript confirmation at the HTTP boundary, recipient/header validation, mandatory customer approval, configured department routing, stale email previews, SMTP acknowledgement, duplicate attempts and uncertain send outcomes. All SMTP calls in tests were mocked; no email was sent.

These tests check specific behaviours. They do not establish complete security or language understanding.

## Browser checks

The business workspace revision was also checked in Chrome: order-reference search, urgency filtering, approved-only copy actions, submitted-case reports by default, separate training data, service settings, operational help and mobile overflow. Personal build content was removed from the business interface. These are functional checks, not independent customer acceptance.

The app was exercised in local headless Chrome at desktop and 390-pixel mobile widths. Verified:

1. Late refund routes to Finance with a draft.
2. Approval requires human acknowledgement and persists.
3. A safety concern cannot be downgraded to low urgency/general support.
4. Investigation signals open their source complaints.
5. Markdown report downloads, and the decision log displays events.
6. An absent OpenAI key shows an error rather than silently returning an AI-labelled rule result.
7. Mobile layout has no horizontal overflow; no JavaScript exceptions were observed.

Screenshots show actual offline demo runs. Expected validation errors were deliberately triggered. No live OpenAI request or live SMTP submission was tested.

## Offline classification evaluation

Reproduce with `python scripts/evaluate.py`. Full predictions: [evaluation-results.json](evaluation-results.json).

The original data uses `vague`, which is normalised to `unclear`. For multi-label examples, “primary matches” means the primary prediction is in the expected label set; it does not prove the priority order is correct.

| Dataset | Primary matches | Exact label sets |
|---|---:|---:|
| 75 original generated examples | 75/75 | 74/75 |
| 20 hand-written challenges | 17/20 | 17/20 |

Known failures:

- **C072:** an extra late-delivery label is inferred alongside damage/refund. Multi-issue language needs more context.
- **T17:** “wobbles dangerously when my child sits down” is classified as unclear, not a possible safety incident. It is flagged uncertain, but the safety phrase detector misses it. A person must still assess the full message.
- **T18:** “a long gouge” is unclear rather than damage.
- **T19:** “paid for oak and you sent walnut” is unclear rather than a wrong item.

I kept these failures visible rather than tuning the rules until the challenge score looked perfect. Rules cannot cover all wording. Even structured AI outputs can be wrong. No independently written holdout dataset has been tested, and these scores should not be used as production claims.

## My first live AI check

1. Run the app and enter my API key privately. Select OpenAI without fallback.
2. Submit a synthetic refund case. Check the engine/model label, exact evidence and team.
3. Submit a safety case and an ambiguous case. Check urgent protection and uncertainty.
4. Try a message telling the model to ignore instructions. Check quotes and classification manually; this is not a full prompt-injection evaluation.
5. Remove the key or use an invalid one. Confirm a visible error and no misleading AI-labelled result.
6. Record the date, model, expected labels, actual outputs, cost from my provider dashboard and all failures. Do not describe OpenAI accuracy until measured on a separately labelled set.

## Remaining limits

Safety detection has known false negatives and simple negation handling. A model may return plausible but incorrect labels or unsupported summaries even when schema and quotes are valid. Draft checks catch only selected unverified claims, not every misleading statement a reviewer might type. The local app has no user authentication, rate limits, encrypted database or production deployment configuration. The reviewer name is not a verified identity. Keep it on loopback with synthetic data.

Report thresholds are deliberately simple: at least three cases and 1.3× the assumed courier order share for selected signals. These are investigation prompts, not statistical significance tests. Missing shipment denominators, product mix and planted synthetic patterns prevent causal conclusions.


## Connected workflow revision

The light dashboard opens first. Browser checks covered its actual metrics, 14 daily bars, training disclosure, investigation drill-through and opening an urgent case. A separate synthetic acceptance database was used, with fictional names, orders and non-deliverable `.invalid` email addresses. Screenshots do not represent real customers or a real support queue.

The image upload was attached to a case and remained visible during review. Requesting transcription without an API key produced a clear error. The customer preview used the supplied address only after approval; the department preview used a configured test Finance mailbox. Sending remained disabled because no SMTP connection was supplied. Desktop and 390-pixel mobile checks showed no horizontal page overflow or JavaScript exceptions.

The manager brief is rules-based. No financial ROI, handling-time savings, service-level compliance, resolution rate, live image-reading accuracy or inbox delivery is claimed.

## 11 November 2026 · Screenshot details and Gmail setup

Nine additional tests cover source-backed identity suggestions, ambiguous details, no guessed identities, private Gmail configuration, preserved existing settings, redacted results, invalid input and mocked authentication without sending. User-provided screenshots also showed one successful live OpenAI classification and one screenshot transcription; those observations are smoke checks, not a measured accuracy evaluation. Gmail authentication and delivery still require the user’s private app password and a live test.

## Light workspace refresh - 12 November 2026

64 regression tests passed. Headless Chrome checks covered the priority-first layout, light colour scheme, complaint submission, explicit human approval, customer and department email previews with delivery disabled, fixture-based screenshot-detail confirmation, and 390px mobile overflow. All new screenshots use synthetic records.
