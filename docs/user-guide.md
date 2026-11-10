# Support team user guide

Customer Support Hub · Demo configuration: Hearthwood Home, a fictional furniture store.
## Start with the dashboard

The dashboard opens first. Review urgent and ageing cases, then click a case to open its review. Waiting 24+ hours means time since intake, not an agreed deadline. Approved means the draft was checked, not that the customer issue is resolved. The manager brief is calculated by rules; it is not an AI-generated report. Refresh to update it.

Choose the training dataset only for synthetic familiarisation. It has no pending review work. Investigation links open the supporting complaint records.

## Record a complaint

Open Complaint desk. Paste the customer's original wording and add known details. Do not replace the source message with assumptions. Select Triage complaint and review the proposed category, team, urgency and quotes. The result is a suggestion, not an executed action.

## Add image evidence

Expand Add complaint image or photo evidence. Upload one PNG/JPEG up to 2 MB. The image is stored locally and attached when the case is created. Removing it from intake does not delete the uploaded local record; retention management is not implemented.

For a screenshot, click Extract screenshot text. This sends the image to OpenAI. Check and edit the transcript, use it in the complaint, then confirm that it matches the source before triage. Blurred or unreadable content may be missed or misread. A product photo without complaint text should be retained as evidence while the complaint is typed manually.

## Review and approve

Open Review queue. Use search and the status/urgency filters to locate a case. Pending cases are ordered by urgency, then newest first. Read the original message and evidence. Edit the route or draft where needed. Enter your reviewer name and a decision note. Notes are required for changes, uncertainty and safety escalation.

Check the acknowledgement before approving. An approved reply can be copied into your existing support system for manual sending. A rejected reply is retained in history and has no copy action. Final decisions are locked against repeat approval. If another window changed a case, reload before continuing.

The reviewer name is an audit label, not a verified staff identity. Do not use it as proof of access authorisation.

## Escalate safety concerns

Read every case for potential hazards. The automated detector can miss dangerous wording. Flagged incidents stay urgent and routed to Product Safety. Explain the escalation in the note, then contact the appropriate colleague using the organisation's actual incident procedure. The tool does not contact that colleague for you.

## Investigate patterns

Complaint insights opens on submitted cases. The report uses a 28-day window ending on the latest complaint date. Counts are based on primary categories. Supporting messages are available under each signal. A signal is a reason to investigate, not proof of fault.

The training dataset is deliberately synthetic and read-only. It is available for familiarisation only. Courier shares are scenario assumptions, not measured shipment denominators.

## Service problems

Open Service settings. With no API connection, choose offline rules. OpenAI failures are shown explicitly. Rules fallback is used only when permitted and remains labelled. When a suggestion is uncertain, ask the customer for clarification rather than inventing facts.

## Exports

Export case reviews downloads submitted records as CSV. Download report creates a Markdown investigation report for the selected dataset. Both may contain complaint details; handle exports according to your data policy.


## Email a customer or department

After approval, choose Preview customer reply. A customer address must have been supplied at intake. Check To, Subject and the full message. Enter a sending reviewer name, confirm the checkbox and choose Send this email. Sending is disabled without a configured SMTP connection.

For an internal escalation, choose Preview department handoff. The destination comes from the server's category-to-mailbox configuration; addresses are never guessed. A pending case may be escalated internally after explicit review, which allows safety concerns to reach the responsible team without waiting for a customer reply. Rejected cases cannot be sent. Internal emails include the source complaint and the suggested summary. Images remain local and are not attached.

The outbox records preview, submitting, submitted or unknown. Submitted means the mail server accepted the message, not that the recipient read or received it. A timeout may happen after acceptance, so unknown or submitting states must be checked against the provider log using the Message-ID. Repeated send attempts are blocked. Do not work around that protection by sending another copy until the original outcome is established.

A sent email does not close the complaint or confirm the department acted. Those actions still need to be tracked in the support process.

## Confirm details from a screenshot

After extraction, review the suggested customer name, email, order and product. Each suggestion includes the source text and shows the current form value. Edit or deselect fields as needed. Nothing replaces form values until Confirm and apply selected details is clicked after checking the confirmation box. This also applies the reviewed transcript. Ambiguous senders, multiple order references and multiple products are left for manual selection. If the transcript changes, refresh suggestions before applying. These details are visible-text suggestions, not a customer-database lookup.
