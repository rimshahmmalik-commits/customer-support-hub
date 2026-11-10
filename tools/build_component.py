"""Rebuild the Streamlit component from the normal desktop interface."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
target=root/'demo_component'
target.mkdir(exist_ok=True)
for name in ('index.html','style.css','app.js','favicon.svg'):
    shutil.copyfile(root/'web'/name,target/name)
html=(target/'index.html').read_text(encoding='utf-8')
html=html.replace('href="/favicon.svg"','href="favicon.svg"').replace('href="/style.css"','href="style.css"').replace('<script src="/app.js" defer></script>','<script src="streamlit-bridge.js"></script><script src="app.js" defer></script>')
(target/'index.html').write_text(html,encoding='utf-8')
js=(target/'app.js').read_text(encoding='utf-8').replace('async function api(path,body){','async function api(path,body){\n if(window.StreamlitDemoBridge)return window.StreamlitDemoBridge.request(path,body);')
(target/'app.js').write_text(js,encoding='utf-8')
