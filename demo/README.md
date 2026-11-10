# Public demo deployment

This branch runs the original Python application with a separate signed-cookie SQLite workspace for each visitor. Each session is seeded with synthetic data, expires after inactivity and can be reset independently. Session and image counts are bounded. Free-host restarts clear all temporary demo state.

Dockerfile.demo and render.yaml target a free Render web service. No private .env, local database or Gmail credentials enter the build. Email sending and Gmail setup are blocked server-side; mailboxes in previews are non-deliverable demo addresses.

Default classification is the existing offline rules engine. Live OpenAI is disabled. An owner may separately configure OPENAI_API_KEY and DEMO_ENABLE_OPENAI=1. The server then locks the model and limits calls to 3 per session and 20 per UTC day per instance. Instance restarts reset these counters; these are not billing-account spend limits. No key should ever be entered by a visitor. Image transcription is unavailable while live OpenAI is disabled.

This is a synthetic-data evaluation sandbox, not production customer-support hosting. Do not put real customer records in it.
