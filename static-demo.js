/* Browser edition: precomputed evidence, visitor-local reviews, no server writes. */
(function (root) {
  'use strict';
  const states = ['needs_review', 'awaiting_evidence', 'confirmed_error', 'valid_charge'];
  const done = s => ['confirmed_error', 'valid_charge'].includes(s);
  const clone = x => JSON.parse(JSON.stringify(x));
  function createStore(seed, storage, key) {
    const rows = seed.report.contracts.flatMap(c => c.lines.map(r => ({...r, contract_id:c.contract_id})));
    function read() {
      const raw = storage.getItem(key);
      if (raw === null) return {version:1, nextId:1, events:[]};
      let value;
      try { value = JSON.parse(raw); } catch { throw Error('Saved demo data is unreadable. Use Reset demo to start again.'); }
      if (value?.version !== 1 || !Number.isSafeInteger(value.nextId) || value.nextId < 1 || !Array.isArray(value.events) || !value.events.every(e => Number.isSafeInteger(e.id) && e.id > 0 && e.id < value.nextId && states.includes(e.status) && typeof e.evidence_key === 'string' && typeof e.reviewer === 'string' && typeof e.note === 'string')) throw Error('Saved demo data is invalid. Use Reset demo to start again.');
      return value;
    }
    function save(input) {
      if (!input || !states.includes(input.status)) throw Error('Choose a valid review decision.');
      if (typeof input.reviewer !== 'string' || !input.reviewer.trim() || input.reviewer.length > 100) throw Error('Enter a reviewer name (up to 100 characters).');
      if (typeof input.note !== 'string' || input.note.length > 4000) throw Error('Notes must be at most 4,000 characters.');
      if (done(input.status) && !input.note.trim()) throw Error('Add a reason for your decision.');
      const row = rows.find(r => r.evidence_key === input.evidence_key);
      if (!row) throw Error('Evidence changed or finding no longer exists. Refresh before saving.');
      const data = read(), previous = data.events.find(e => e.evidence_key === row.evidence_key);
      const reviewer = input.reviewer.trim(), note = input.note.trim();
      if (previous && previous.status === input.status && previous.reviewer === reviewer && previous.note === note) return {saved:false, unchanged:true};
      if (input.expected_version !== (previous?.id || 0)) throw Error('Another review was saved. Refresh before saving your changes.');
      data.events.unshift({id:data.nextId++, evidence_key:row.evidence_key, contract_id:row.contract_id, line_id:row.line_id, status:input.status, reviewer, note, created_at:new Date().toISOString()});
      try { storage.setItem(key, JSON.stringify(data)); } catch { throw Error('Browser storage is unavailable or full. Your review was not saved.'); }
      return {saved:true};
    }
    function reset() {
      let nextId=1;
      try { nextId=read().nextId; } catch { /* Explicit reset is the recovery path. */ }
      storage.setItem(key, JSON.stringify({version:1, nextId, events:[]}));
    }
    function snapshots() {
      const events=read().events, latest=new Map();
      events.forEach(e=>{if(!latest.has(e.evidence_key))latest.set(e.evidence_key,e.status);});
      const status=r=>latest.get(r.evidence_key)||'needs_review';
      const analysis=clone(seed.analysis), geography=clone(seed.geography);
      for (const c of analysis.contracts) {
        const flagged=rows.filter(r=>r.contract_id===c.contract_id&&r.requires_review);
        c.statuses={}; flagged.forEach(r=>{const s=status(r);c.statuses[s]=(c.statuses[s]||0)+1;});
        c.completed=flagged.filter(r=>done(status(r))).length;
        c.remaining=flagged.length-c.completed;c.progress=flagged.length?100*c.completed/flagged.length:null;
        c.outstanding_known_difference_pence=flagged.filter(r=>!done(status(r))&&r.discrepancy_pence!==null).reduce((n,r)=>n+r.discrepancy_pence,0);
      }
      for(const c of geography.contracts) for(const loc of c.locations) {
        loc.remaining=rows.filter(r=>r.contract_id===c.contract_id&&loc.job_ids.includes(r.job_id)&&r.requires_review&&!done(status(r))).length;
      }
      return {analysis,geography};
    }
    return {events:()=>read().events, save, reset, snapshots};
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports={createStore}; return; }
  const base = new URL('.', document.currentScript.src);
  const ready = fetch(new URL('data.json',base)).then(r=>{if(!r.ok)throw Error('Could not load the demo examples.');return r.json();});
  let storePromise = ready.then(seed=> {
    // No clear(), cookies or keys belonging to the personal website are touched.
    const key='clearcost:'+base.pathname+':'+seed.dataset_id+':reviews:v1';
    let storage;
    try { storage=window.localStorage; } catch { storage={getItem(){throw Error('Enable browser storage to use reviews.');},setItem(){throw Error('Browser storage is blocked.');}}; }
    return {store:createStore(seed,storage,key),key};
  });
  async function locked(key, action) {
    if (!navigator.locks) throw Error('This browser cannot safely save concurrent reviews. Use a current browser on HTTPS or localhost.');
    return navigator.locks.request(key,action);
  }
  root.demoFetch = async function(input, options={}) {
    try {
      const seed=await ready, {store,key}=await storePromise;
      const path=new URL(String(input),base).pathname;
      let value;
      if(path.endsWith('/api/report')) value=seed.report;
      else if(path.endsWith('/api/extraction-links')) value=seed.links;
      else if(path.endsWith('/api/map-outline')) return fetch(new URL('uk-outline.json',base));
      else if(path.endsWith('/api/reviews')) value=options.method==='POST'?await locked(key,()=>store.save(JSON.parse(options.body))):store.events();
      else if(path.endsWith('/api/analysis')) value=store.snapshots().analysis;
      else if(path.endsWith('/api/geography')) value=store.snapshots().geography;
      else throw Error('Unknown browser demo data request.');
      return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
    } catch(e) { return new Response(JSON.stringify({error:e.message}),{status:400,headers:{'Content-Type':'application/json'}}); }
  };
  root.ClearcostDemo={ready};
  document.addEventListener('DOMContentLoaded',()=>{
    const panel=document.createElement('section');panel.setAttribute('aria-label','Browser demo session');
    panel.style.cssText='padding:14px 18px;margin:0 0 22px;border:1px solid #cbd6c8;border-radius:10px;background:#edf3e6;display:flex;align-items:center;gap:16px;flex-wrap:wrap';
    panel.innerHTML='<div style="flex:1;min-width:190px"><strong>Your browser demo</strong><p style="margin:4px 0;font-size:13px">Reviews stay in this browser, across tabs and visits. Other browsers start independently. No review data is sent to a server.</p></div><button type="button" id="reset-demo" style="padding:10px 16px;border:1px solid #8ba481;border-radius:8px;cursor:pointer">Reset demo</button><p id="demo-reset-error" role="alert"></p>';
    const host=document.querySelector('main')||document.body;const header=host.querySelector('.portfolio-header');if(header)header.after(panel);else host.prepend(panel);
    const dialog=document.createElement('dialog');dialog.style.cssText='max-width:440px;border:1px solid #9bb98d;border-radius:12px;padding:24px;color:#19352e';
    dialog.setAttribute('aria-labelledby','reset-demo-title');
    dialog.innerHTML='<h2 id="reset-demo-title">Reset your demo reviews?</h2><p>This removes your saved reviews for this demo in this browser. Unsaved edits will also be discarded. The example evidence stays unchanged.</p><div style="display:flex;gap:12px;margin-top:18px"><button id="cancel-demo-reset" autofocus>Keep my reviews</button><button id="confirm-demo-reset">Reset my reviews</button></div>';
    document.body.append(dialog);
    panel.querySelector('button').onclick=()=>dialog.showModal();
    dialog.querySelector('#cancel-demo-reset').onclick=()=>dialog.close();
    dialog.querySelector('#confirm-demo-reset').onclick=async()=>{
      try { const {store,key}=await storePromise;await locked(key,()=>store.reset());root.dispatchEvent(new Event('clearcost-reset'));location.reload(); }
      catch(e){dialog.close();document.getElementById('demo-reset-error').textContent=e.message;}
    };
  });
})(typeof window === 'undefined' ? globalThis : window);
