/* Streamlit's documented component protocol, with serial request/response delivery. */
(() => {
  let active = null, tail = Promise.resolve(), ready;
  const readyPromise = new Promise(resolve => ready = resolve);
  const post = (type, payload = {}) => parent.postMessage({isStreamlitMessage: true, type, ...payload}, '*');
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.type !== 'streamlit:render') return;
    ready();
    const result = event.data.args?.result;
    if (active && result?.id === active.id) {
      const job = active; active = null; clearTimeout(job.timer);
      result.ok ? job.resolve(result.data) : job.reject(new Error(result.data?.error || 'The demo could not complete this request.'));
    }
  });
  window.StreamlitDemoBridge = {request(path, body) {
    const job = () => readyPromise.then(() => new Promise((resolve, reject) => {
      const id = crypto.randomUUID();
      active = {id, resolve, reject, timer: setTimeout(() => {active = null; reject(new Error('The demo is taking too long. Refresh before retrying a change.'));}, 90000)};
      post('streamlit:setComponentValue', {value: {id, path, method: body === undefined ? 'GET' : 'POST', body}, dataType: 'json'});
    }));
    const promise = tail.then(job, job); tail = promise.catch(() => {}); return promise;
  }};
  document.addEventListener('click', async event => {
    const anchor = event.target.closest('a[href^="/api/"]');
    if (!anchor) return;
    event.preventDefault();
    try {
      const data = await window.StreamlitDemoBridge.request(anchor.getAttribute('href'));
      const file = data.download;
      if (!file) throw new Error('No export was returned.');
      const url = URL.createObjectURL(new Blob([file.text], {type: file.mime}));
      const link = document.createElement('a'); link.href = url; link.download = file.filename;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (error) {alert(error.message);}
  });
  post('streamlit:componentReady', {apiVersion: 1});
  const resize = () => post('streamlit:setFrameHeight', {height: Math.max(850, Math.min(1800, document.documentElement.scrollHeight))});
  window.addEventListener('load', () => {resize(); new ResizeObserver(resize).observe(document.body);});
})();
