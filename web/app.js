'use strict';
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label=s=>String(s).replace(/_/g,' ');
let allCases=[],selectedCase=null,currentPage='dashboard',config={};
async function api(path,body){
 const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw new Error(data.error||'The local app could not complete this request.');return data;
}
function error(message){$('#global-error').textContent=message;$('#global-error').hidden=false;}
function clearError(){$('#global-error').hidden=true;}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,3500);}
async function refreshCases(){allCases=await api('/api/cases');$('#pending-count').textContent=allCases.filter(x=>x.status==='pending').length;}
async function openPage(page){
 clearError();currentPage=page;document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!=='page-'+page);
 document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
 if(page==='dashboard')await renderDashboard();
 if(page==='queue'){await refreshCases();renderQueue();}
 if(page==='patterns')await renderReport();
 if(page==='history')await renderEvents();
 window.scrollTo({top:0,behavior:'instant'});
}
document.querySelectorAll('.nav').forEach(button=>button.addEventListener('click',()=>openPage(button.dataset.page).catch(e=>error(e.message))));
$('.brand').addEventListener('click',e=>{e.preventDefault();openPage('dashboard');});
const examples={
 damage:{customer:'Priya Shah',product:'Oslo 3-seater sofa',courier:'ParcelPath',order_id:'HW-10428',message:'The sofa arrived yesterday with a split along the wooden frame and a torn box. I have photos. Can someone help with the next steps?'},
 refund:{customer:'Tom Becker',product:'Malmo wardrobe',courier:'SwiftDrop',order_id:'HW-20513',message:'The wardrobe was delivered on time and was not damaged. I returned it three weeks ago and my refund still has not reached my account.'},
 safety:{customer:'Aisha Khan',product:'Malmo wardrobe',courier:'ParcelPath',order_id:'HW-30871',message:'The wardrobe tipped over during normal use and my partner was hurt. We have stopped using it. Please tell me who can investigate this.'},
 unclear:{customer:'Liam O\'Connor',product:'Linden desk',courier:'',order_id:'',message:'I have contacted you before and this still is not sorted. Please get back to me.'}
};
document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>{
 const row=examples[button.dataset.example];$('#customer').value=row.customer;$('#product').value=row.product;$('#courier').value=row.courier;$('#order').value=row.order_id;$('#message').value=row.message;
}));
$('#engine').addEventListener('change',()=>{const live=$('#engine').value==='openai';$('#openai-settings').hidden=!live;$('#engine-summary').textContent=live?'OpenAI · API usage applies':'Offline rules · no API cost';});
$('#triage-form').addEventListener('submit',async event=>{
 event.preventDefault();clearError();const button=$('#triage-button');button.disabled=true;button.textContent='Reading the complaint…';
 try{
  if(imageBusy)throw new Error('Wait for the image upload or extraction to finish.');
  const complaint={customer:$('#customer').value,customer_email:$('#customer-email').value,product:$('#product').value,courier:$('#courier').value,order_id:$('#order').value,message:$('#message').value};
  const row=await api('/api/triage',{complaint,engine:$('#engine').value,model:$('#model').value,api_key:$('#api-key').value,allow_fallback:$('#fallback').checked,image_id:pendingImage?.id||null,image_text_reviewed:$('#image-reviewed').checked});
  renderResult(row);clearImage();await refreshCases();toast('Saved for review. Nothing was sent.');
 }catch(e){error(e.message);}
 finally{button.disabled=false;button.innerHTML='Triage complaint <span>→</span>';}
});
function renderResult(row){
 const r=row.result;$('#result-status').textContent='PENDING REVIEW';
 $('#result').innerHTML=`<div class="tag-row"><span class="pill ${esc(r.urgency)}">${esc(r.urgency.toUpperCase())}</span><span class="pill">${esc(label(r.category))}</span><span class="pill quiet">${esc(r.engine)}</span></div>
 ${r.safety_flag?'<div class="error"><b>Possible safety incident.</b> Escalate to Product Safety. The urgent route cannot be downgraded.</div>':''}
 ${r.fallback_reason?`<div class="warning"><b>Rules fallback was used.</b> ${esc(r.fallback_reason)}</div>`:''}
 <div class="summary-text">${esc(r.summary)}</div><p class="result-line">Proposed team: <b>${esc(r.team)}</b></p><p class="result-line">Tone: ${esc(r.sentiment)} · Case ${esc(row.id)}</p>
 ${r.uncertain?`<div class="warning">Needs clarification or careful review. ${esc(r.reason)}</div>`:`<p class="hint">${esc(r.reason)}</p>`}
 <p class="section-label">Evidence in the original message</p>${r.evidence.map(q=>`<blockquote class="evidence">${esc(q)}</blockquote>`).join('')}
 <p class="section-label">Reply draft · not sent</p><div class="draft">${esc(r.draft)}</div><p class="hint">Policy-controlled wording. Proposed steps are not completed actions.</p><button class="button" id="review-this">Review this case →</button>`;
 $('#review-this').addEventListener('click',()=>{selectedCase=row.id;$('#queue-filter').value='pending';$('#queue-search').value='';$('#queue-urgency').value='all';openPage('queue').catch(e=>error(e.message));});
}
$('#queue-filter').addEventListener('change',renderQueue);
$('#queue-search').addEventListener('input',renderQueue);
$('#queue-urgency').addEventListener('change',renderQueue);
function renderQueue(){
 const filter=$('#queue-filter').value;
 const query=$('#queue-search').value.trim().toLowerCase(), urgency=$('#queue-urgency').value;
 const priority={urgent:0,normal:1,low:2};
 const rows=allCases.filter(x=>x.source==='interactive'&&(filter==='all'||x.status===filter)&&(urgency==='all'||x.result.urgency===urgency)&&(!query||[x.id,x.complaint.customer,x.complaint.order_id,x.complaint.message].join(' ').toLowerCase().includes(query))).sort((a,b)=>priority[a.result.urgency]-priority[b.result.urgency]||b.created_at.localeCompare(a.created_at));
 $('#queue-count').textContent=`${rows.length} matching case${rows.length===1?'':'s'} · highest urgency first`;
 if(!rows.some(x=>x.id===selectedCase))selectedCase=rows[0]?.id||null;
 $('#case-list').innerHTML=rows.length?rows.map(row=>`<button class="case-button ${row.id===selectedCase?'selected':''}" data-case="${esc(row.id)}"><small>${esc(row.id)} · ${esc(row.status)}</small><strong>${esc(row.complaint.customer||'Customer name not given')}</strong><span class="pill ${esc(row.result.urgency)}">${esc(row.result.urgency)}</span><span class="hint">${esc(label(row.result.category))}</span></button>`).join(''):'<p class="hint">No cases in this view. Try a complaint in the desk first.</p>';
 document.querySelectorAll('[data-case]').forEach(button=>button.addEventListener('click',()=>{selectedCase=button.dataset.case;renderQueue();}));
 const row=rows.find(x=>x.id===selectedCase);if(!row){$('#review-detail').innerHTML='<div class="empty"><h3>A clear queue.</h3><p>New submissions will appear here. No decisions are made automatically.</p></div>';return;}
 const r=row.result,locked=row.status!=='pending';
 $('#review-detail').innerHTML=`<div class="card-title"><h2>${esc(row.complaint.customer||'Customer complaint')}</h2><span class="pill">${esc(row.status)}</span></div><p class="hint">${esc(row.id)} · ${esc(row.complaint.product)} · ${esc(r.engine)} / ${esc(r.model)}</p>
 <div class="case-message">${esc(row.complaint.message)}</div><p class="hint">Suggested reason: ${esc(r.reason)}</p>
 ${r.safety_flag?'<div class="error">Product Safety · Urgent. A reviewer must explain the escalation.</div>':''}
 <details><summary>Evidence and original suggestion</summary>${r.evidence.map(q=>`<blockquote class="evidence">${esc(q)}</blockquote>`).join('')}<p class="hint">Originally ${esc(label(row.original_result.category))} / ${esc(row.original_result.urgency)}. Original draft and corrections are retained in the decision log.</p></details>
 <form id="review-form"><div class="two"><div><label for="review-category">Category</label><select id="review-category" ${locked?'disabled':''}>${Object.keys(config.teams).map(c=>`<option value="${c}" ${c===r.category?'selected':''}>${esc(label(c))}</option>`).join('')}</select></div><div><label for="review-urgency">Urgency</label><select id="review-urgency" ${locked?'disabled':''}>${['urgent','normal','low'].map(u=>`<option ${u===r.urgency?'selected':''}>${u}</option>`).join('')}</select></div></div>
 <p class="hint">Proposed team: <b id="review-team">${esc(r.team)}</b></p><label for="review-draft">Reply draft <span>for manual use only</span></label><textarea id="review-draft" rows="10" maxlength="6000" ${locked?'readonly':''}>${esc(r.draft)}</textarea>
 <div class="two"><div><label for="reviewer">Reviewer name</label><input id="reviewer" value="${esc(row.reviewer||'')}" placeholder="Your name" maxlength="100" ${locked?'readonly':''}></div><div><label for="review-note">Decision note</label><textarea id="review-note" rows="2" maxlength="2000" placeholder="Explain edits, uncertainty or escalation." ${locked?'readonly':''}>${esc(row.review_note||'')}</textarea></div></div>
 ${locked?`<div class="success">Reviewed by ${esc(row.reviewer)}. Sending status is recorded in email history below.</div>${row.status==='approved'?'<button type="button" class="button" id="copy-draft">Copy approved draft</button>':''}`:`<label class="check"><input id="acknowledged" type="checkbox">I checked the complaint, the route and the draft. Approval does not send it.</label><div class="actions"><button type="button" class="primary" data-decision="approve">Approve draft</button><button type="button" class="button" data-decision="save">Save changes</button><button type="button" class="danger" data-decision="reject">Reject draft</button></div>`}<div id="review-error" role="alert"></div></form><div id="case-extras"></div>`;
 $('#review-category').addEventListener('change',()=>$('#review-team').textContent=config.teams[$('#review-category').value]);
 loadCaseExtras(row).catch(e=>error(e.message));
 if(locked){$('#copy-draft')?.addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('#review-draft').value);toast('Draft copied. Check it before using it.');}catch{toast('Select the draft text and copy it manually.');}});return;}
 document.querySelectorAll('[data-decision]').forEach(button=>button.addEventListener('click',async()=>{
  const buttons=[...document.querySelectorAll('[data-decision]')];buttons.forEach(x=>x.disabled=true);
  try{
   const body={version:row.version,category:$('#review-category').value,urgency:$('#review-urgency').value,draft:$('#review-draft').value,reviewer:$('#reviewer').value,note:$('#review-note').value,decision:button.dataset.decision,acknowledged:$('#acknowledged').checked};
   const reviewed=await api('/api/review/'+row.id,body);toast(reviewed.status==='approved'?'Draft approved. No email was sent.':'Review saved.');
   $('#queue-filter').value=reviewed.status==='pending'?'pending':reviewed.status;await refreshCases();renderQueue();
  }catch(e){$('#review-error').className='error';$('#review-error').textContent=e.message;buttons.forEach(x=>x.disabled=false);}
 }));
}
$('#report-source').addEventListener('change',()=>renderReport().catch(e=>error(e.message)));
async function renderReport(){
 const source=$('#report-source').value;await refreshCases();$('#sample-disclosure').hidden=source!=='sample';const report=await api('/api/report?source='+source);
 $('#report-download').href='/api/report.md?source='+source;
 $('#report-period').textContent=`${report.period_start} to ${report.period_end} · 28-day window anchored to the latest record · ${report.excluded} records outside the window or without valid dates.`;
 $('#report-stats').innerHTML=[['Complaints in window',report.total],['Flagged urgent',report.urgent],['Possible safety cases',report.safety]].map(([name,n])=>`<div class="stat"><b>${n}</b><span>${name}</span></div>`).join('');
 const cats=Object.entries(report.categories).sort((a,b)=>b[1]-a[1]);const max=Math.max(1,...cats.map(x=>x[1]));
 $('#category-bars').innerHTML=cats.length?cats.map(([cat,count])=>`<div class="bar"><div class="bar-label"><span>${esc(label(cat))}</span><span>${count}</span></div><div class="track"><div class="track-fill" data-scale="${count/max}"></div></div></div>`).join(''):'<p class="hint">No cases in this window yet.</p>';
 document.querySelectorAll('[data-scale]').forEach(el=>el.style.transform=`scaleX(${Number(el.dataset.scale)})`);
 $('#trend').innerHTML=`<div class="trend-values"><div><b>${report.damage_trend.previous_14_days}</b><span>Previous 14 days</span></div><div><b>${report.damage_trend.recent_14_days}</b><span>Recent 14 days</span></div></div>`;
 $('#insights').innerHTML=report.insights.length?report.insights.map((signal,i)=>`<article class="card signal"><p class="eyebrow">INVESTIGATION SIGNAL ${String(i+1).padStart(2,'0')}</p><h2>${esc(signal.title)}</h2><p class="observation">${esc(signal.observation)}</p><p>${esc(signal.hypothesis)}</p><p><b>Recommended investigation:</b> ${esc(signal.next_step)}</p><p class="hint">${esc(signal.caveat)}</p><button class="button" data-evidence="${i}">Inspect ${signal.evidence_ids.length} supporting complaints →</button></article>`).join(''):'<article class="card"><h2>No cluster crossed the investigation threshold.</h2><p class="hint">A small or empty dataset does not prove there are no problems.</p></article>';
 $('#evidence-panel').hidden=true;
 document.querySelectorAll('[data-evidence]').forEach(button=>button.addEventListener('click',()=>{
  const signal=report.insights[Number(button.dataset.evidence)];const rows=allCases.filter(x=>signal.evidence_ids.includes(x.id));
  $('#evidence-panel').hidden=false;$('#evidence-panel').innerHTML=`<h2>Evidence · ${esc(signal.title)}</h2>${rows.map(row=>`<div class="evidence-case"><b>${esc(row.id)} · ${esc(row.complaint.product)}</b><br><small>${esc(row.complaint.date||row.created_at.slice(0,10))} · ${esc(row.complaint.courier||'Courier unknown')} · ${esc(label(row.result.category))}</small><p>${esc(row.complaint.message)}</p></div>`).join('')}`;
  $('#evidence-panel').scrollIntoView({behavior:'smooth',block:'start'});
 }));
}
async function renderEvents(){
 const events=await api('/api/events');$('#events').innerHTML=events.length?events.map(row=>`<article class="event"><div class="meta">${esc(row.at)} · ${esc(row.case_id||'No case created')}</div><h3>${esc(label(row.action))}</h3><details><summary>Inspect the recorded details</summary><pre>${esc(JSON.stringify(JSON.parse(row.details),null,2))}</pre></details></article>`).join(''):'<article class="card"><p class="hint">No decisions recorded yet. New submissions and reviews will appear here.</p></article>';
}
(async()=>{
 try{config=await api('/api/config');if(config.app_version!=='2026.11.11.2'){throw new Error('An older Customer Support Hub server is running. Stop the old app process and start this updated installation before uploading or triaging.');}$('#product').innerHTML='<option value="">Not specified</option>'+config.products.map(x=>`<option>${esc(x)}</option>`).join('');$('#model').value=config.model;$('#key-status').textContent=config.key_configured?'A server-side API key is configured. You can leave this field blank.':'No server-side key detected. Enter a key here, or add it privately to .env.';if(config.public_demo)enablePublicDemo();await refreshCases();renderEmailConfig();await openPage('dashboard');}
 catch(e){error(e.message);}
})();


// Manager overview: every number is calculated from stored cases.
$('#dashboard-source').addEventListener('change',()=>renderDashboard().catch(e=>error(e.message)));
$('#dashboard-refresh').addEventListener('click',()=>renderDashboard().catch(e=>error(e.message)));
$('#dashboard-new').addEventListener('click',()=>openPage('desk'));
function openQueueCase(id=null,urgency='all'){
 selectedCase=id;$('#queue-filter').value='pending';$('#queue-search').value='';$('#queue-urgency').value=urgency;
 return openPage('queue');
}
$('#dashboard-queue').addEventListener('click',()=>openQueueCase().catch(e=>error(e.message)));
function ageLabel(hours){return hours===null?'Unknown':hours<1?'Under 1h':hours<24?Math.floor(hours)+'h':Math.floor(hours/24)+'d '+Math.floor(hours%24)+'h';}
async function renderDashboard(){
 const source=$('#dashboard-source').value,d=await api('/api/dashboard?source='+source);
 if($('#dashboard-source').value!==source)return;
 $('#dashboard-training').hidden=source!=='sample';$('#dashboard-empty').hidden=d.total!==0;
 $('#dashboard-updated').textContent='Updated '+new Date(d.generated_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
 const cards=source==='sample'?[['Training complaints',d.total,'Read-only synthetic records','neutral'],['Flagged urgent',d.report.urgent,'Classification flags, not a live queue','red'],['Damage complaints',d.report.categories.damaged_item||0,'Primary category · 28-day window','amber'],['Investigation signals',d.report.insights.length,'Open the supporting evidence','teal']]:[['Awaiting review',d.pending,'Pending review decisions','neutral'],['Urgent awaiting review',d.urgent_pending,'Check these cases first','red'],['Waiting 24+ hours',d.aged_pending,'Intake age, not a service deadline','amber'],['Approved drafts',d.approved,'Approval does not mean resolved','teal']];
 $('#dashboard-metrics').innerHTML=cards.map(([name,value,note,tone])=>`<div class="metric-card ${tone}"><span>${esc(name)}</span><strong>${value}</strong><small>${esc(note)}</small></div>`).join('');
 const max=Math.max(1,...d.daily.map(x=>x.count));
 $('#dashboard-chart').innerHTML=d.daily.map(x=>`<div class="day-column" title="${esc(x.date)}: ${x.count} complaints"><span class="day-count">${x.count||''}</span><div class="day-track"><div class="day-fill" data-height="${x.count/max}"></div></div><span class="day-label">${Number(x.date.slice(8))}</span></div>`).join('');
 document.querySelectorAll('[data-height]').forEach(el=>el.style.height=Math.max(2,Number(el.dataset.height)*100)+'%');
 $('#dashboard-chart-range').textContent=d.daily[0].date+' to '+d.daily.at(-1).date+' · date window ends at the latest recorded complaint';
 $('#dashboard-brief').innerHTML=d.brief.length?d.brief.map((b,i)=>`<button class="brief-item" data-brief="${i}"><span class="brief-count">${b.count}</span><span><b>${esc(b.title)}</b><small>${esc(b.action)}</small></span><span>↗</span></button>`).join(''):source==='sample'?'<p class="hint">Training history has no pending human reviews. Investigate the complaint patterns below; no review completion is implied.</p>':'<p class="hint">No urgent, ageing or uncertain reviews currently need attention. Check the queue for other pending work.</p>';
 document.querySelectorAll('[data-brief]').forEach(button=>button.addEventListener('click',()=>openQueueCase(d.brief[Number(button.dataset.brief)].case_ids[0]).catch(e=>error(e.message))));
 $('#dashboard-attention').innerHTML=d.attention.length?d.attention.map(c=>`<tr><td><b>${esc(c.customer)}</b><small>${esc(c.id)}</small></td><td>${esc(label(c.category))}<small>${esc(c.product)}</small></td><td>${esc(c.team)}</td><td>${esc(ageLabel(c.age_hours))}</td><td><span class="pill ${esc(c.urgency)}">${esc(c.urgency)}</span></td><td><button class="table-action" data-open-case="${esc(c.id)}">Review ↗</button></td></tr>`).join(''):`<tr><td colspan="6" class="table-empty">${source==='sample'?'Training records are not pending work. Switch to submitted complaints to manage reviews.':'No pending cases. New complaints will appear here.'}</td></tr>`;
 document.querySelectorAll('[data-open-case]').forEach(button=>button.addEventListener('click',()=>openQueueCase(button.dataset.openCase).catch(e=>error(e.message))));
 $('#dashboard-signals').innerHTML=d.report.insights.length?d.report.insights.slice(0,3).map((x,i)=>`<div class="mini-signal"><span class="pill quiet">${x.evidence_ids.length} source cases</span><h3>${esc(x.title)}</h3><p>${esc(x.observation)}</p><button class="table-action" data-dashboard-signal="${i}">Open investigation →</button></div>`).join(''):'<p class="hint">No cluster meets the investigation threshold. This does not establish that there are no underlying problems.</p>';
 document.querySelectorAll('[data-dashboard-signal]').forEach(button=>button.addEventListener('click',async()=>{try{$('#report-source').value=source;await openPage('patterns');document.querySelector(`[data-evidence="${button.dataset.dashboardSignal}"]`)?.click();}catch(e){error(e.message);}}));
 const productMax=Math.max(1,...d.products.map(x=>x.count));
 $('#dashboard-products').innerHTML=d.products.length?d.products.map(x=>`<div class="product-row"><div><span>${esc(x.name)}</span><b>${x.count}</b></div><progress value="${x.count}" max="${productMax}">${x.count}</progress></div>`).join(''):'<p class="hint">Product counts will appear after intake.</p>';
 $('#dashboard-scope').textContent=d.total+' records in selected dataset · '+d.note;
}

// Images stay local unless the operator explicitly requests OpenAI extraction.
let pendingImage=null,imageBusy=false,imageGeneration=0,imageOperations=0;
function clearImage(){imageGeneration++;pendingImage=null;$('#complaint-image').value='';$('#image-evidence').hidden=true;$('#image-extraction').hidden=true;$('#image-preview').removeAttribute('src');$('#image-text').value='';$('#image-reviewed').checked=false;$('#image-error').textContent='';$('#image-details-review').hidden=true;}
$('#remove-image').addEventListener('click',clearImage);
$('#complaint-image').addEventListener('change',async()=>{
 const file=$('#complaint-image').files[0],generation=++imageGeneration;pendingImage=null;$('#image-details-review').hidden=true;$('#image-evidence').hidden=true;$('#image-extraction').hidden=true;$('#image-reviewed').checked=false;$('#image-error').textContent='';
 if(!file)return;
 imageOperations++;imageBusy=true;
 try{
  if(!['image/png','image/jpeg'].includes(file.type)||file.size>2000000)throw Error('Choose a PNG or JPEG image up to 2 MB.');
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
  const uploaded=await api('/api/images',{name:file.name,data});if(generation!==imageGeneration)return;
  pendingImage=uploaded;$('#image-preview').src=uploaded.url;$('#image-name').textContent=uploaded.name+' · '+Math.round(uploaded.bytes/1024)+' KB · local evidence';$('#image-evidence').hidden=false;
 }catch(e){$('#image-error').className='error';$('#image-error').textContent=e.message||'Image upload failed.';}
 finally{imageOperations--;imageBusy=imageOperations>0;}
});
$('#extract-image').addEventListener('click',async()=>{
 if(!pendingImage||imageBusy)return;const generation=imageGeneration;imageOperations++;imageBusy=true;$('#extract-image').disabled=true;
 try{
  const result=await api('/api/extract-image',{image_id:pendingImage.id,api_key:$('#api-key').value,model:$('#model').value});if(generation!==imageGeneration)return;
  $('#image-text').value=result.text;$('#image-notes').textContent=result.notes||'Review the image and transcript carefully. AI can misread text.';$('#image-extraction').hidden=false;$('#image-reviewed').checked=false;await reviewImageDetails();
 }catch(e){$('#image-error').className='error';$('#image-error').textContent=e.message;}
 finally{imageOperations--;imageBusy=imageOperations>0;$('#extract-image').disabled=false;}
});
$('#use-image-text').addEventListener('click',()=>{if(!$('#image-text').value.trim()){toast('No complaint text found. Type the original complaint and retain the photo as evidence.');return;}$('#message').value=$('#image-text').value;toast('Text added. Check it against the image before triage.');});

function renderEmailConfig(){
 const cfg=config.email||{};
 $('#email-config-status').innerHTML=`<span class="pill ${cfg.configured?'low':'normal'}">${cfg.configured?'SMTP configured':'Email not connected'}</span><p class="hint">${cfg.sender?'Sender: '+esc(cfg.sender):'No sender configured'}</p><p class="hint">${Object.keys(cfg.teams||{}).length} department routes configured. Credentials are never shown here.</p>`;
}
async function loadCaseExtras(row){
 const container=$('#case-extras');
 const [evidence,messages]=await Promise.all([api('/api/case-evidence/'+row.id),api('/api/messages/'+row.id)]);
 if(selectedCase!==row.id||!container.isConnected)return;
 container.innerHTML=`${evidence.length?`<div class="case-evidence"><h3>Image evidence</h3>${evidence.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener"><img src="${esc(x.url)}" alt="${esc(x.name)}"></a><p class="hint">${esc(x.name)} · stored with case · SHA-256 ${esc(x.sha256.slice(0,12))}…</p>`).join('')}</div>`:''}<div class="email-section"><h3>Email handoff</h3><p class="hint">Check the recipient and full message before sending. Images are not attached to email.</p><div class="actions">${row.status==='approved'?'<button class="button" type="button" data-email-kind="customer">Preview customer reply</button>':''}${row.status!=='rejected'?'<button class="button" type="button" data-email-kind="department">Preview department handoff</button>':''}</div>${row.status==='pending'?'<p class="hint">Approve the draft to enable customer email. Internal escalation can be reviewed and sent before customer approval.</p>':''}<div id="email-preview-panel"></div><div id="email-action-error" role="alert"></div><div class="message-history">${messages.map(m=>`<p><span class="pill">${esc(m.state)}</span> ${esc(m.kind)} → ${esc(m.recipient)}<br><small>Message-ID: ${esc(m.message_id)}</small></p>`).join('')}</div></div>`;
 container.querySelectorAll('[data-email-kind]').forEach(button=>button.addEventListener('click',async()=>{
  button.disabled=true;$('#email-action-error').textContent='';
  try{
   const m=await api('/api/email-preview',{case_id:row.id,kind:button.dataset.emailKind});
   if(selectedCase!==row.id)return;
   $('#email-preview-panel').innerHTML=`<article class="email-preview"><div class="tag-row"><span class="pill">${esc(m.state)}</span><span class="pill quiet">${esc(m.kind)}</span></div><label>To<input value="${esc(m.recipient)}" readonly></label><label>Subject<input value="${esc(m.subject)}" readonly></label><label>Message<textarea rows="10" readonly>${esc(m.body)}</textarea></label><p class="hint">Message-ID: ${esc(m.message_id)}</p>${!m.smtp_configured?'<p class="warning">Sending is unavailable until SMTP is configured privately on the server.</p>':''}${m.state!=='preview'?'<p class="warning">This message was already attempted. Check its state and the provider log; automatic retries are blocked.</p>':''}<label for="email-reviewer">Sending reviewer<input id="email-reviewer" maxlength="100" placeholder="Your name" value="${esc(row.reviewer||'')}"></label><label class="check"><input id="email-confirm" type="checkbox">I checked the recipient and full message and want to send this email now.</label><button type="button" class="primary" id="email-send" ${!m.smtp_configured||m.state!=='preview'?'disabled':''}>Send this email</button></article>`;
   $('#email-send').addEventListener('click',async()=>{
    const send=$('#email-send');send.disabled=true;
    try{const result=await api('/api/email-send',{outbox_id:m.id,reviewer:$('#email-reviewer').value,acknowledged:$('#email-confirm').checked});toast(result.message);await loadCaseExtras(row);}
    catch(e){$('#email-action-error').className='error';$('#email-action-error').textContent=e.message;await loadCaseExtras(row);$('#email-action-error').className='error';$('#email-action-error').textContent=e.message;}
   });
  }catch(e){$('#email-action-error').className='error';$('#email-action-error').textContent=e.message;}
  finally{button.disabled=false;}
 }));
}


// Suggestions are a preview. No identity field changes until explicit confirmation.
let detailsTranscript=null;
const intakeFieldIds={customer:'customer',customer_email:'customer-email',order_id:'order',product:'product'};
const intakeFieldLabels={customer:'Customer name',customer_email:'Customer email',order_id:'Order reference',product:'Product'};
async function reviewImageDetails(){
 const transcript=$('#image-text').value;if(!transcript.trim()){$('#image-details-review').hidden=true;return;}
 const suggestions=await api('/api/suggest-details',{text:transcript});
 if($('#image-text').value!==transcript)return;
 detailsTranscript=transcript;const panel=$('#image-details-review');panel.hidden=false;
 panel.innerHTML=`<h3>Confirm customer details</h3><p class="hint">${esc(suggestions.note)} Selected fields will replace their current values. The reviewed transcript will also become the complaint text.</p>${Object.entries(suggestions.fields).map(([key,field])=>{const current=$('#'+intakeFieldIds[key]).value;return `<div class="detail-suggestion"><label class="check"><input type="checkbox" data-apply-field="${key}" ${field.value?'checked':''}>Apply ${esc(intakeFieldLabels[key])}</label><p class="hint">Current: ${esc(current||'Not supplied')}${current&&field.value&&current!==field.value?' · will be replaced if selected':''}</p>${key==='product'?`<select id="suggest-${key}"><option value="">Not specified</option>${config.products.map(x=>`<option ${x===field.value?'selected':''}>${esc(x)}</option>`).join('')}</select>`:`<input id="suggest-${key}" type="${key==='customer_email'?'email':'text'}" maxlength="${key==='customer_email'?254:key==='order_id'?60:100}" value="${esc(field.value)}">`}<p class="hint">${esc(field.note)}</p>${field.evidence?`<blockquote class="evidence">${esc(field.evidence)}</blockquote>`:''}</div>`;}).join('')}<label class="check"><input id="confirm-image-details" type="checkbox">I checked the transcript and selected customer details against the screenshot.</label><button type="button" class="primary" id="apply-image-details">Confirm and apply selected details</button><p id="image-details-status" role="status"></p>`;
 $('#apply-image-details').addEventListener('click',()=>{
  const status=$('#image-details-status');status.className='error';
  if($('#image-text').value!==detailsTranscript){status.textContent='The transcript changed. Refresh the suggested details before applying them.';return;}
  if(!$('#confirm-image-details').checked){status.textContent='Confirm that you checked the transcript and selected details first.';return;}
  const selected=[...panel.querySelectorAll('[data-apply-field]:checked')];
  for(const item of selected){const input=$('#suggest-'+item.dataset.applyField);if(!input.checkValidity()){input.reportValidity();status.textContent='Correct the selected details before applying.';return;}}
  selected.forEach(item=>{$('#'+intakeFieldIds[item.dataset.applyField]).value=$('#suggest-'+item.dataset.applyField).value.trim();});
  $('#message').value=detailsTranscript;$('#image-reviewed').checked=true;status.className='success';status.textContent=selected.length+' selected fields applied. Review the form, then triage the complaint.';
  toast('Confirmed details and complaint text applied.');
 });
}
$('#review-image-details').addEventListener('click',()=>reviewImageDetails().catch(e=>{error(e.message);}));
$('#image-text').addEventListener('input',()=>{$('#image-reviewed').checked=false;const confirmation=$('#confirm-image-details');if(confirmation)confirmation.checked=false;});

// Gmail credentials stay in this local app. A login test never sends mail.
$('#gmail-save').addEventListener('click',async()=>{
 const button=$('#gmail-save'),result=$('#gmail-setup-result');button.disabled=true;result.textContent='Saving connection…';
 try{const response=await api('/api/gmail-configure',{address:$('#gmail-address').value,app_password:$('#gmail-app-password').value});$('#gmail-app-password').value='';config.email=response.email;renderEmailConfig();result.className='success';result.textContent=response.message;}
 catch(e){result.className='error';result.textContent=e.message;}
 finally{button.disabled=false;}
});
$('#gmail-test').addEventListener('click',async()=>{
 const button=$('#gmail-test'),result=$('#gmail-setup-result');button.disabled=true;result.className='hint';result.textContent='Checking encrypted Gmail login. No email will be sent…';
 try{const response=await api('/api/gmail-test',{});result.className='success';result.textContent=response.message;}
 catch(e){result.className='error';result.textContent=e.message;}
 finally{button.disabled=false;}
});

function enablePublicDemo(){
 document.body.classList.add('demo-public');document.querySelector('#public-demo-banner').hidden=false;
 document.querySelector('#demo-ai-note').textContent=config.key_configured?'Limited live OpenAI requests are available.':'Classification uses the offline rules engine; live OpenAI transcription is not connected.';
 document.querySelector('.sidebar-foot').innerHTML='<span class="dot"></span> PUBLIC SANDBOX<p>Fictional data · private session<br>Resettable · email preview only</p>';
 document.querySelector('#api-key').value='';document.querySelector('#api-key').disabled=true;
 document.querySelector('#engine option[value="openai"]').disabled=!config.key_configured;
 document.querySelector('#extract-image').disabled=!config.key_configured;
 document.querySelector('#reset-demo').addEventListener('click',async()=>{if(!confirm('Reset your own demo changes and restore the fictional cases?'))return;try{await api('/api/demo/reset',{});location.reload();}catch(e){error(e.message);}});
}
