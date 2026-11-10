# Email and image integrations

Customer Support Hub · Demo configuration: Hearthwood Home, a fictional furniture store.
## Optional SMTP connection

Configure the following privately in `.env`, then restart the app:

```text
SMTP_HOST=your-provider-host
SMTP_PORT=587
SMTP_USER=your-mailbox-login
SMTP_PASSWORD=your-private-app-password
SMTP_FROM=your-verified-sender-address
```

Use the exact host and account settings supplied by the mail provider. Port 587 uses STARTTLS; 465 uses implicit TLS. Plaintext SMTP is not supported. No credentials are displayed in the UI. Some accounts require an app password or a provider-specific setup; this adapter does not implement OAuth sign-in.

Configure only mailboxes the organisation has verified:

```text
TEAM_EMAIL_PRODUCT_SAFETY=
TEAM_EMAIL_DAMAGED_ITEM=
TEAM_EMAIL_LATE_DELIVERY=
TEAM_EMAIL_MISSING_PARTS=
TEAM_EMAIL_WRONG_ITEM=
TEAM_EMAIL_REFUND_DELAY=
TEAM_EMAIL_ASSEMBLY_HELP=
TEAM_EMAIL_UNCLEAR=
```

Blank routes cannot be used for department handoff. Different categories may share the same real department inbox. Test customer replies and department handoffs using controlled test mailboxes before supplying customer addresses. No live SMTP connection was tested in this delivery.

## Sending guarantees and limits

The server freezes To, Subject and Body in a saved preview. Customer previews require an approved draft. Internal previews can be created for pending cases, but explicit human confirmation is still required. A version check rejects a preview when the case has changed. Each case/version/destination-kind gets a single send attempt; repeated requests are blocked before the network call.

The message has a stored Message-ID. Successful SMTP submission is recorded as submitted, not delivered. Exceptions after an attempt are marked unknown conservatively. A process interruption can leave submitting. In both cases, verify the provider log before any manual retry. This is duplicate-attempt protection, not a promise of exactly-once inbox delivery. There is no automatic retry, bounce handling, delivery webhook or inbox/thread synchronisation.

Only the text preview is emailed. Local evidence images are not attached. A sent handoff does not assign a real helpdesk ticket, confirm department acceptance or resolve the complaint.

## Image evidence and transcription

One PNG/JPEG up to 2 MB may be attached at intake. The local database stores its bytes, name, MIME type, hash and optional extracted text. The upload endpoint checks size and file signature. It does not perform a complete image parser/security scan. Keep untrusted uploads in a controlled local trial until stronger file handling is reviewed.

Upload alone does not contact OpenAI. Extract screenshot text explicitly sends the image with `store: false` using the configured model and API key. That flag does not guarantee zero provider retention. The API may charge for the image. The service asks for transcription, not a diagnosis of damage or its cause. It can still misread text; operator confirmation is required before triage after extraction. No live image extraction was tested in this delivery.

Official implementation reference: [OpenAI Images and vision](https://developers.openai.com/api/docs/guides/images-vision?api-mode=responses).

## Data handling

Customer email addresses, source complaints, evidence images, transcripts and email content are local records, so backups and exports must be protected. Removed/unsubmitted uploads remain stored locally; there is no retention policy or cleanup interface yet. Complete the organisation's privacy, access and retention review before introducing live personal data.

## Gmail setup in the interface

Service settings → Email connection → Connect Gmail accepts the sending address and a Google app password in a private password field. Save writes the SMTP settings to the local Git-ignored `.env`, preserves unrelated settings and clears the password field. Test login authenticates over encrypted SMTP without sending any message. A successful test is not proof of delivery; send a separately reviewed message to a controlled test address afterward. Google app passwords require 2-Step Verification and may be unavailable for some accounts. Do not use the normal Google account password. See [Google app-password guidance](https://support.google.com/accounts/answer/185833).

The Gmail connector in this chat cannot transfer account credentials into the standalone app. Its local SMTP connection is separate.
