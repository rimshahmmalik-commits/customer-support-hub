# Card-free deployment

Streamlit Community Cloud: sign in with GitHub, select repository
`rimshahmmalik-commits/customer-support-hub`, branch `live-demo`, and entry file
`demo_streamlit.py`. Select Python 3.12. No secrets or payment card are required
for the default offline demo.

This entry file embeds the existing interface as a Streamlit component. Browser
commands go to the original Python handlers through `hearthwood/streamlit_transport.py`.
It is a transport adapter, not a separate implementation of triage or reporting.
Each Streamlit session gets its own signed, temporary SQLite workspace. Changes
are lost when the free host restarts. Never upload real customer information.

Email drafts, review decisions, dashboard insights, image attachments, CSV and
Markdown exports work. Sending email and connecting accounts are blocked on the
server. OpenAI classification and screenshot transcription are disabled until an
owner privately configures an API key and explicitly enables the limited AI mode.
The demo openly labels its default keyword-rule engine; it does not pretend to
use an LLM. No local credentials are included.

The component assets mirror `web/`; run `python tools/build_component.py` after
changing the normal interface, then commit both source and generated assets.

Local run: `streamlit run demo_streamlit.py`. Original desktop app remains
`python app.py`; the Streamlit entry always uses isolated public-demo mode.
