# Administrator handover

Customer Support Hub · Demo configuration: Hearthwood Home, a fictional furniture store.
## Delivered scope

Single-device, loopback-only complaint intake, suggested classification, controlled reply templates, review approval/rejection, search, priority filtering, local audit history, manager dashboard, image evidence, reviewable screenshot transcription, explicit SMTP email handoff, investigation signals and CSV/Markdown exports. This is the deliverable's supported installation model. It is not a hosted multi-user service.

## Configuration

Copy `.env.example` to `.env` and configure the optional `OPENAI_API_KEY`, `OPENAI_MODEL` and `HEARTHWOOD_PORT`. Restart after changing server settings. The default port is 8004. Session connection settings in the interface do not persist across page reloads. Keys entered in the password field are not saved to cases, exports or audit history. Clear the field or close/reload the page after use on a shared device.

The OpenAI service receives the complaint and optional customer/order/product/courier details. Requests use Responses API structured extraction and `store: false`. That setting does not guarantee zero provider retention. Confirm provider terms, legal basis and organisational privacy requirements before supplying customer information. No live API acceptance test was possible during this build.

## Storage and backup

SQLite records are stored at `runtime/hearthwood.sqlite3`. Stop the service before copying the database for a consistent backup. Keep backups access-controlled. To restore, stop the app, preserve the current database, replace it with the backup, then restart and verify a known case. Never overwrite a database while the service is writing to it. No retention/deletion workflow or automatic backup schedule is included.

## Known service boundaries

No staff authentication or roles, public hosting, encrypted database, inbox synchronisation, payment execution or real ticket assignment is included. The server binds only to 127.0.0.1; do not expose it through a public tunnel or change it to a public interface. A hosted team deployment needs a separate authentication, security, privacy and deployment workstream.

Automated language checks can miss risks. Reviewer names are unverified audit labels. Human review remains mandatory. The sample dataset is fictional and clearly separate from submitted cases. Report courier ratios are based on assumed 60/40 overall shares and are not fault or damage-rate estimates.

## Acceptance checklist

- Launch on the target device and confirm automatic browser opening.
- Submit a synthetic complaint and verify it enters the pending queue.
- Search by order reference, then filter and review it.
- Verify an approved reply can be copied and a rejected reply cannot.
- Confirm urgent safety cases cannot be downgraded.
- Inspect the decision history and export a report.
- Enter an API key privately for a live service check before accepting OpenAI classification.
- Back up and restore the local database using synthetic records before operational use.

Regression results and known classification failures are recorded in `verification.md`. Live OpenAI testing, backup restoration on the target machine and independent holdout testing remain outstanding; do not present these as completed.

## Integration and image storage

See `integrations.md` for SMTP, department mailboxes and screenshot extraction. Attachments, transcripts and outbox records are stored inside the same SQLite database. This increases backup size and includes potentially sensitive data. No image retention, orphan-upload cleanup, mail delivery webhook, bounce processing or email thread synchronisation is implemented. Images receive basic type/signature and size checks, not a complete content-security scan.

Do not treat SMTP acceptance as customer delivery or a resolved complaint. Check ambiguous sending states manually; this version deliberately does not retry them. Department messages do not include image attachments or externally accessible evidence links.
