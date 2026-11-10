"""Card-free hosting entry point. Run: streamlit run demo_streamlit.py."""
import os
from pathlib import Path
os.environ['DEMO_PUBLIC'] = '1'
os.environ.setdefault('DEMO_ENABLE_OPENAI', '0')
import streamlit as st
import streamlit.components.v1 as components
from hearthwood.streamlit_transport import dispatch

st.set_page_config(page_title='Customer Support Hub | Demo', page_icon='💬', layout='wide')
st.markdown('<style>.block-container{padding:0 .5rem 0;max-width:100%}header[data-testid="stHeader"]{display:none}</style>', unsafe_allow_html=True)
component = components.declare_component('customer_support_hub', path=str(Path(__file__).parent / 'demo_component'))
command = component(result=st.session_state.get('_last_result'), key='support_workspace', default=None)
if command and command.get('id') != st.session_state.get('_last_command'):
    try:
        result, cookie = dispatch(command, st.session_state.get('_demo_cookie', ''))
        st.session_state['_demo_cookie'] = cookie
    except Exception as exc:
        result = {'id': command.get('id'), 'ok': False, 'data': {'error': str(exc) if isinstance(exc, ValueError) else 'The demo could not process this request. Please refresh and try again.'}}
    st.session_state['_last_command'] = command.get('id')
    st.session_state['_last_result'] = result
    st.rerun()
