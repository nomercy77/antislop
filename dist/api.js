/* Optional FastAPI adapter. Server sessions and permissions are authoritative. */
(() => {
  'use strict';
  const A = window.A, raw = String(window.ANTISLOP_CONFIG?.apiBaseUrl || '').trim();
  if (!raw) return;
  let base, configError='';
  try {
    const url = new URL(raw);
    if (url.username || url.password || url.search || url.hash || !(url.protocol === 'https:' || (url.protocol === 'http:' && ['localhost','127.0.0.1','[::1]'].includes(url.hostname)))) throw new Error();
    base = url.href.replace(/\/$/, '').replace(/\/api$/, '');
  } catch { configError='API configuration requires an HTTPS URL or a loopback HTTP URL.'; }
  A.live = true; A.authenticated = false; A.apiLoading = true; A.apiError = '';
  A.persist = () => {}; // Authenticated data is not copied to localStorage.
  let serverRole = null, serverPermissions = null, serverVerification = null;
  const reset = () => { serverRole=null;serverPermissions=null;serverVerification=null;A.state = {role:'submitter', user:{name:'',email:''}, reviews:[], experts:[], application:null, applications:[], events:[], activeReview:null}; };
  reset();
  const e = A.esc, icon = A.icon, btn = A.btn;
  const data = form => Object.fromEntries(new FormData(form).entries());
  const list = (value, key) => Array.isArray(value) ? value : value?.[key] || [];
  const err = '<p id="flow-error" class="error" role="alert" aria-live="polite"></p>';
  const field = (label, name, value = '', attrs = '') => `<div class="field"><label for="live-${name}">${e(label)}</label><input id="live-${name}" name="${e(name)}" value="${e(value)}" ${attrs}></div>`;
  const select = (label,name,choices,value) => `<div class="field"><label for="live-${name}">${e(label)}</label><select id="live-${name}" name="${e(name)}" ${name==='category'?'required':''}>${choices.map(([v,label])=>`<option value="${e(v)}" ${v===value?'selected':''}>${e(label)}</option>`).join('')}</select></div>`;
  const area = (label,name,value='') => `<div class="field full"><label for="live-${name}">${e(label)}</label><textarea id="live-${name}" name="${e(name)}" required maxlength="3000">${e(value)}</textarea></div>`;
  const submit = label => `<button type="submit" class="btn primary">${e(label)}</button>`;
  const heading = (title,sub,action='') => `<div class="page-heading"><div class="heading-copy"><div class="eyebrow">ANTISLOP WORKSPACE</div><h1>${e(title)}</h1><p>${e(sub)}</p></div><div class="heading-actions">${action}</div></div>`;
  const goto = (label,route,kind='secondary') => btn(e(label),'dashboard-go',kind,`data-route="${e(route)}"`);
  const authFrame = body => `<div class="auth-layout"><aside class="auth-brand"><div class="logo"><span class="logo-mark">${icon('shield')}</span>antislop</div><h1>Better code.<br>Greater confidence.</h1><p>Connect your team, your code, and the people reviewing it.</p></aside><section class="auth-form">${body}</section></div>`;
  const role = () => ['coder','submitter'].includes(A.context.authRole) ? A.context.authRole : 'submitter';
  const allowedRoutes = {
    submitter:new Set(['overview','reviews','experts','repositories','messages','billing','settings','new-review','review','profile']),
    coder:new Set(['overview','reviews','verification','messages','billing','settings','review','profile']),
    team:new Set(['overview','team','settings'])
  };
  const roleLabels={submitter:'Code submitter',coder:'Coder / doer',team:'Verification staff'};
  function can(permission){
    if(!A.authenticated||!serverRole)return false;
    if(serverPermissions)return serverPermissions.includes(permission);
    const fallback={submitter:['create_review','read_own_reviews','assign_reviewer','request_repository_access','read_review_messages','send_review_messages'],coder:['apply_verification','read_own_reviews'],team:['read_verification_queue','decide_verification']};
    if(serverRole==='coder'&&serverVerification==='approved'&&['read_assigned_reviews','browse_opportunities','read_review_messages','send_review_messages'].includes(permission))return true;
    return fallback[serverRole]?.includes(permission)||false;
  }
  function requirePermission(permission){if(!can(permission))throw new Error('Your account does not have permission to perform this action.');}
  A.hasPermission=can;
  function fail(message, form) {
    const target = form?.querySelector('[role="alert"]') || document.querySelector('.modal [role="alert"]') || document.getElementById('flow-error');
    if (target) target.textContent = message; else A.toast(message);
  }
  async function request(path, options={}) {
    if(configError) throw new Error(configError);
    const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),15000);
    try {
      const response = await fetch(`${base}/api${path}`, {credentials:'include', ...options, headers:{Accept:'application/json', ...(options.body?{'Content-Type':'application/json'}:{}), ...options.headers}, signal:controller.signal});
      let body = {}; try { body = await response.json(); } catch {}
      if (!response.ok) {
        if(response.status===401 && A.authenticated){reset();A.authenticated=false;A.context={};A.go('register');}
        const detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map(x=>x.msg).join('; ') : body.message || `Request failed (${response.status}).`;
        const error = new Error(detail); error.status=response.status; throw error;
      }
      return body;
    } catch (error) {
      if (error.name==='AbortError') throw new Error('The API took too long to respond. Please retry.');
      if (error instanceof TypeError) throw new Error('Cannot reach the API. Check its address, network, and allowed frontend origin.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  const post = (path, body) => request(path,{method:'POST',body:JSON.stringify(body)});
  async function pending(form, task) {
    if(form.dataset.pending==='true') return;
    form.dataset.pending='true';const buttons=[...form.querySelectorAll('button[type="submit"]')]; buttons.forEach(x=>{x.disabled=true;x.setAttribute('aria-busy','true');});
    fail('',form);
    try { await task(); } catch(error) { fail(error.message,form); }
    finally { delete form.dataset.pending;buttons.forEach(x=>{x.disabled=false;x.removeAttribute('aria-busy');}); }
  }
  function normalizeReview(r) { return {...r, category:A.category(r.category).id, expertId:r.expertId ?? r.reviewer_id ?? null, expertAccess:r.expertAccess || r.reviewer_access || 'pending', access:r.access || 'pending',findings:r.findings||[], proposals:r.proposals||[],messages:r.messages||[]}; }
  function normalizeExpert(x) { return {...x,id:x.id||x.user_id, initials:x.initials||(x.name||'').split(/\s+/).slice(0,2).map(s=>s[0]).join(''),title:x.title||x.specialty||'Code reviewer', skills:x.skills||[x.specialty||'Code review'],bio:x.bio||'',verified:x.verified??x.status==='approved',rate:x.rate||0,color:x.color||''}; }
  async function hydrate() {
    const response=await request('/auth/me'); const user=response.user||response;
    if(!user.id || !['submitter','coder','staff','team'].includes(user.role)) throw new Error('The API returned an invalid authenticated user.');
    reset();serverRole=['staff','team'].includes(user.role)?'team':user.role;serverPermissions=Array.isArray(user.permissions)?Object.freeze([...user.permissions]):null;serverVerification=user.verification_status||null;A.state.user=user;A.state.role=serverRole;A.authenticated=true;
    const tasks=[request('/reviews').then(async x=>{A.state.reviews=list(x,'reviews').map(normalizeReview);A.state.activeReview=A.state.reviews[0]?.id||null;if(A.state.activeReview)await refreshReview(A.state.activeReview);}),request('/experts').then(x=>{A.state.experts=list(x,'experts').map(normalizeExpert);}),request('/events').then(x=>{A.state.events=list(x,'events').map(event=>({...event,icon:'file',time:event.created_at?new Date(event.created_at*1000).toLocaleString():'Recorded activity'}));})];
    if(user.role==='coder') tasks.push(request('/coder/applications/me').then(async x=>{A.state.application=x.application??(x.id?x:null);serverVerification=A.state.application?.status||null;A.state.opportunities=[];if(A.state.application?.status==='approved'){const result=await request('/opportunities');A.state.opportunities=list(result,'opportunities').map(x=>({...x,category:A.category(x.category).id}));}}).catch(error=>{if(error.status!==404)throw error;}));
    if(A.state.role==='team') tasks.push(request('/staff/applications').then(x=>{A.state.applications=list(x,'applications');}));
    const results=await Promise.allSettled(tasks); const failed=results.find(x=>x.status==='rejected');
    if(failed) throw failed.reason;
  }
  async function refreshReview(id) {
    const response=await request(`/reviews/${encodeURIComponent(id)}`);const r=normalizeReview(response.review||response);
    if(r.verificationSubmissionId){const verification=await request(`/reviews/${encodeURIComponent(id)}/verification`);r.verification=verification.submission||null;}
    const index=A.state.reviews.findIndex(x=>x.id===r.id);if(index<0)A.state.reviews.unshift(r);else A.state.reviews[index]=r;
    A.state.activeReview=r.id; return r;
  }
  const noService = () => A.toast('This operation is not connected to a backend service yet. No changes were made.');
  // Explicitly close every prototype write path when an API is configured.
  ['confirm-demo-access','google-demo','reset-demo','confirm-reset','demo-dashboard','explore-experts','finding-status','apply-review','billing-info','notifications','help','learn-workflow'].forEach(name=>{A.actions[name]=noService;});
  ['submit-proposal','save-settings'].forEach(name=>{A.forms[name]=async form=>fail('This operation is not supported by the API yet. No changes were made.',form);});
  A.inputs.evidence=()=>A.toast('File uploads are not supported yet. Include a portfolio link instead.');
  A.views.register=()=>{
    const d=A.context.registration||{},r=role(),ready=!A.apiLoading&&!A.apiError;
    return authFrame(`<div class="eyebrow">YOUR NEXT STEP STARTS HERE</div><h1>Join Antislop</h1><p>Register or sign in securely using your email or Google account.</p><p class="auth-foot">Choose a workspace for a new account. This option cannot change an existing account’s role. Staff access is provisioned separately.</p>${A.apiError?`<div class="notice amber">${e(A.apiError)}</div>${btn('Retry connection','api-retry','secondary')}`:''}<div class="role-cards">${[['submitter','I have code to review','folder'],['coder','I’m a coder / doer','code']].map(([v,l,s])=>`<button type="button" class="role-card ${r===v?'active':''}" data-action="auth-role" data-role="${v}">${icon(s)}<strong>${l}</strong><small>${v==='coder'?'Request expert verification.':'Submit a repository for review.'}</small></button>`).join('')}</div><form data-form="register">${field('Full name','name',d.name||'','required autocomplete="name" maxlength="100"')}${field('Email address','email',d.email||'','type="email" required autocomplete="email" maxlength="254"')}${err}<button class="btn primary" type="submit" ${!ready||!A.apiConfig?.auth?.email_otp?'disabled':''}>${A.apiLoading?'Connecting…':'Continue with email'}</button></form>${ready&&!A.apiConfig?.auth?.email_otp?'<p class="auth-foot">Email OTP delivery is not configured.</p>':''}<div class="or">or</div>${btn('<span class="google-icon">G</span> Continue with Google','google-login','secondary',!ready||!A.apiConfig?.auth?.google?'disabled':'')}${ready&&!A.apiConfig?.auth?.google?'<p class="auth-foot">Google sign-in is not configured.</p>':''}<p class="auth-foot">Your session is managed securely by the API.</p>`);
  };
  A.views.otp=()=>authFrame(`<div class="eyebrow">VERIFY YOUR EMAIL</div><h1>Check your inbox</h1><p>Enter the verification code sent to <strong>${e(A.context.registration?.email||'your email')}</strong>.</p><form data-form="otp">${field('6-digit code','otp','','required inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" class="otp-input"')}${err}${submit('Verify and continue')}</form><p class="auth-foot"><button data-action="demo-resend">Resend code</button> · <button data-action="go" data-route="register">Change email</button></p>`);
  A.forms.register=async form=>pending(form,async()=>{if(A.authenticated)throw new Error('Sign out before registering a different account.');const d=data(form);const registration={name:String(d.name||'').trim(),email:String(d.email||'').trim(),role:role()};await post('/auth/otp/request',registration);A.context.registration=registration;A.go('otp');});
  A.forms.otp=async form=>pending(form,async()=>{if(A.authenticated)throw new Error('You already have an authenticated session.');if(!A.context.registration?.email)throw new Error('Request a new code from the registration page.');await post('/auth/otp/verify',{email:A.context.registration.email,code:String(data(form).otp||'')});await hydrate();A.context.registration=null;A.go(A.state.role==='coder'?'verification':'overview');});
  A.actions['demo-resend']=async el=>{el.disabled=true;try{if(!A.context.registration)throw new Error('Return to registration to request a code.');await post('/auth/otp/request',A.context.registration);A.toast('A new verification code was sent.');}catch(error){fail(error.message);}finally{el.disabled=false;}};
  A.actions['google-login']=()=>{if(A.authenticated){A.go('overview');return;}if(!A.apiConfig?.auth?.google)return noService();location.assign(`${base}/api/auth/google/start?role=${encodeURIComponent(role())}`);};
  A.actions['auth-role']=el=>{
    if(A.authenticated){A.toast('Your account role is managed by the server.');return;}
    if(!['submitter','coder'].includes(el.dataset.role))return;
    const form=document.querySelector('[data-form="register"]');
    if(form){const values=data(form);A.context.registration={name:values.name||'',email:values.email||''};}
    A.context.authRole=el.dataset.role;A.render();
  };
  A.actions.signout=async()=>{try{await post('/auth/logout',{});reset();A.authenticated=false;A.context={};A.go('register');}catch(error){A.toast(error.message);}};
  A.views['new-review']=()=>{const d=A.context.reviewDraft||{};return `${heading('Create a code review','Pin the code revision, choose an assurance level, and queue verification.')}<section class="panel form-panel"><form data-form="review-wizard"><div class="form-grid">${field('Review title','title',d.title||'','required maxlength="100"')}${select('Task category','category',A.categories.map(x=>[x.id,x.label]),A.category(d.category).id)}${select('Primary stack','stack',[['TypeScript','TypeScript / Node.js'],['Python','Python']],d.stack||'TypeScript')}${select('Verification level','verificationLevel',[['baseline','Syntax check'],['analysis','Static analysis, AST/CFG, and type safety']],d.verificationLevel||'analysis')}${field('GitHub repository URL','repo',d.repo||'','type="url" required placeholder="https://github.com/owner/repository"')}${field('Full commit SHA','sha',d.sha||'','required pattern="[a-fA-F0-9]{40}" minlength="40" maxlength="40"')}${select('Visibility','visibility',[['private','Private'],['public','Public']],d.visibility||'private')}${field('Review budget (USD)','budget',d.budget||'','type="number" min="1" max="1000000" required')}${field('Preferred deadline','deadline',d.deadline||'','type="date" required')}${area('Review scope and acceptance criteria','scope',d.scope||'')}</div><div class="notice">${icon('shield')}<p>The selected plan is queued against this immutable SHA. A worker must be running to execute it. Private repositories require a future GitHub App integration.</p></div><label class="check-label"><input type="checkbox" name="authorized" required>I have permission to request review and share access to this repository.</label>${err}<div class="form-actions">${goto('Cancel','overview')}${submit('Create review and queue verification')}</div></form></section>`;};
  A.forms['review-wizard']=async form=>pending(form,async()=>{requirePermission('create_review');const d=data(form);if(!A.categories.some(category=>category.id===d.category))throw new Error('Choose one of the listed task categories.');if(!/^[a-fA-F0-9]{40}$/.test(String(d.sha||'')))throw new Error('Enter the full 40-character commit SHA.');const language=d.stack==='Python'?'python':'javascript';const capabilities=d.verificationLevel==='baseline'?['syntax']:['syntax','static-analysis','ast-cfg','formal.type-safety'];const response=await post('/reviews',{title:d.title,repo:d.repo,category:A.category(d.category).id,sha:d.sha,stack:d.stack,scope:d.scope,budget:Number(d.budget),deadline:d.deadline,visibility:d.visibility,verification_languages:[language],verification_capabilities:capabilities});const r=normalizeReview(response.review||response);A.state.reviews.unshift(r);A.state.activeReview=r.id;A.go('review');A.toast('Review created and verification queued.');});
  const originalViews={...A.views};
  // Reuse the visual dashboard components, while removing prototype-only wording.
  function liveCopy(html){
    const replacements=[
      ['This preview records access confirmations locally. It does not connect to GitHub or grant repository permissions.','The API stores access requests. GitHub access remains unverified until an integration confirms it.'],
      ['Messages are stored in this browser only. No email or external notification is sent.','Messages are stored by the API. Email notifications are not configured.'],
      ['Updates are saved to this browser for the preview.','Profile editing is not connected yet. Your account details come from the authenticated API session.'],
      ['Local preview preferences','Account details'],
      ['Editing this demo profile does not verify ownership of the address.','Email changes require a new ownership verification flow.'],
      ['Your demo profile is approved. You can explore the proposal workflow.','Your profile is approved. Assigned reviews will appear in your workspace.'],
      ['Sample opportunities','Available reviews'],['Preview assignments','Current assignments'],
      ['Your workspace activity will appear here.','No workspace activity yet.'],
      ['Illustrative sample findings','Findings returned by the review service'],
      ['Assigned reviews','Your assigned reviews'],
      ['Mock billing','Payment service not connected'],['Local demo','Shared conversation'],
      ['GitHub installation, Google sign-in, email OTP delivery, and team permissions need connected backend services before production use.','Authentication and staff permissions are enforced by the API. GitHub grants, AI execution, and payments still require their own integrations.'],
      ['No payments connected','Payment service not connected'],
      ['$0<small> / hr</small>','Scoped<small> review</small>'],
      ['<strong>$0</strong><small> / hour</small>','<strong>Scope-based</strong><small> estimate</small>']
    ];
    replacements.forEach(([from,to])=>{html=html.replaceAll(from,to);});
    return html.replace(/\bSample\b/g,'Current').replace(/\bsample\b/g,'current').replace(/\bDemo\b/g,'Recorded').replace(/\bdemo\b/g,'recorded').replace(/\bPreview\b/g,'Account').replace(/\bpreview\b/g,'workspace');
  }
  ['overview','reviews','experts','repositories','review','messages','billing','settings'].forEach(name=>{const original=originalViews[name];if(original)A.views[name]=()=>liveCopy(original());});
  const liveReviews=A.views.reviews;
  A.views.reviews=()=>{
    const html=liveReviews();if(A.state.role!=='coder')return html;
    const opportunities=A.state.opportunities||[];
    return html+`<section class="panel" style="margin-top:24px"><div class="panel-head"><div><h2>Available review opportunities</h2><p>Private repository links and briefs are shared only after assignment.</p></div></div>${A.state.application?.status!=='approved'?'<div class="notice amber" style="margin:20px">Your verification application must be approved before you can view available opportunities.</div>':opportunities.length?`<div class="table-scroll"><table><thead><tr><th>REVIEW</th><th>STACK</th><th>BUDGET</th><th>DEADLINE</th></tr></thead><tbody>${opportunities.map(x=>`<tr><td>${e(x.title)}<div class="repo-category">${A.categoryBadge(x)}</div></td><td>${e(x.stack)}</td><td>$${e(x.budget)}</td><td>${e(x.deadline)}</td></tr>`).join('')}</tbody></table></div><div class="notice" style="margin:20px">Proposal submission is not connected yet. A submitter can select your approved profile through the expert directory.</div>`:'<div class="empty"><p>No unassigned reviews are available yet.</p></div>'}</section>`;
  };
  A.views.verification=()=>{const x=A.state.application,d=A.context.applicationDraft||x||{};const showForm=!x||A.context.verificationEditing||['changes_requested','rejected'].includes(x.status);return `${heading('Coder verification','A separate staff team reviews your experience and supporting links.')}<section class="panel form-panel">${x?`<div class="notice">${icon('shield')}<div><strong>${e(x.status.replaceAll('_',' '))}</strong>${x.notes?`<p>${e(x.notes)}</p>`:''}</div></div>`:''}${showForm?`<form data-form="verification"><div class="form-grid">${field('Full name','name',d.name||A.state.user.name,'required maxlength="100"')}${field('Contact email','email',A.state.user.email,'type="email" readonly')}${field('GitHub profile','github',d.github||'','type="url" required')}${select('Experience','experience',[['0–2 years','0–2 years'],['3–5 years','3–5 years'],['6–10 years','6–10 years'],['10+ years','10+ years']],d.experience||'3–5 years')}${select('Specialty','specialty',[['Application security','Application security'],['Backend & APIs','Backend & APIs'],['Frontend & accessibility','Frontend & accessibility'],['Infrastructure & reliability','Infrastructure & reliability'],['Testing & quality','Testing & quality']],d.specialty||'Application security')}${field('Portfolio URL','portfolio',d.portfolio||'','type="url" required')}${area('Review experience','bio',d.bio||'')}</div><label class="check-label"><input type="checkbox" name="consent" required>I agree to the verification team reviewing these details and confirm they are accurate.</label>${err}<div class="form-actions">${submit(x?'Resubmit application':'Submit application')}</div></form>`:`<p class="muted">${x.status==='approved'?'Your application is approved. Assignment and access remain scoped to each review.':'Your application is waiting for the staff team. Their decision will appear here.'}</p><div class="card-actions">${btn('Update application','edit-application','secondary')}${goto('View reviews','reviews','primary')}</div>`}</section>`;};
  A.forms.verification=async form=>pending(form,async()=>{requirePermission('apply_verification');const d=data(form),body={name:d.name,github:d.github,experience:d.experience,specialty:d.specialty,portfolio:d.portfolio,bio:d.bio,consent:d.consent==='on'};const response=await post('/coder/applications',body);A.state.application=response.application||response;await hydrate();A.context.applicationDraft=null;A.context.verificationEditing=false;A.render();A.toast('Application submitted for staff review.');});
  A.views.team=()=>`${heading('Verification queue','Authenticated staff decisions are recorded by the API.')}<section class="panel"><div class="verification-list" style="padding:20px">${A.state.applications.map(x=>`<article class="verification-item"><div class="info"><h3>${e(x.name)}</h3><p>${e(x.specialty)} · ${e(x.experience)}</p></div>${A.tag(x.status)}${btn('Review application','team-review','secondary',`data-id="${e(x.id)}"`)}</article>`).join('')||'<div class="empty"><h3>No applications yet</h3></div>'}</div></section>`;
  A.actions['team-review']=el=>{if(!can('read_verification_queue'))return A.toast('Staff access is required.');const x=A.state.applications.find(item=>item.id===el.dataset.id);if(!x)return;A.context.staffApplicationId=x.id;A.modal(`Review ${x.name}`,'Check supporting evidence before deciding.',`<p>${e(x.bio)}</p><div class="kv"><span>GitHub</span><span>${e(x.github)}</span></div><div class="kv"><span>Portfolio</span><span>${e(x.portfolio)}</span></div><form data-form="team-decision">${select('Decision','decision',[['approved','Approve'],['changes_requested','Request changes'],['rejected','Decline']],'approved')}${area('Decision notes','notes',x.notes||'')}${err}${submit('Save decision')}</form>`);};
  A.forms['team-decision']=async form=>pending(form,async()=>{requirePermission('decide_verification');const d=data(form);await request(`/staff/applications/${encodeURIComponent(A.context.staffApplicationId)}`,{method:'PATCH',body:JSON.stringify({decision:d.decision,notes:d.notes})});const response=await request('/staff/applications');A.state.applications=list(response,'applications');A.closeModal();A.render();A.toast('Verification decision saved.');});
  A.forms['confirm-hire']=async form=>pending(form,async()=>{requirePermission('assign_reviewer');const d=data(form);await post(`/reviews/${encodeURIComponent(d.reviewId)}/assign`,{reviewer_id:d.expertId});await refreshReview(d.reviewId);A.closeModal();A.go('review');A.toast('Reviewer assigned. GitHub access is a separate step.');});
  A.actions['hire-expert']=el=>{if(!can('assign_reviewer'))return A.toast('Only the code submitter can select a reviewer.');const x=A.state.experts.find(item=>item.id===el.dataset.id);if(!x)return;A.modal('Assign reviewer',x.name,`<form data-form="confirm-hire"><input type="hidden" name="expertId" value="${e(x.id)}">${select('Review','reviewId',A.state.reviews.map(r=>[r.id,r.title]),el.dataset.review||A.state.activeReview)}<div class="notice">Assignment does not grant repository access or create a payment.</div>${err}${submit('Assign reviewer')}</form>`);};
  A.actions['expert-profile']=el=>{const x=A.state.experts.find(item=>item.id===el.dataset.id);if(!x)return;A.modal(x.name,x.title,`<p>${e(x.bio)}</p><div class="kv"><span>GitHub profile</span><span>${e(x.github||'Not supplied')}</span></div><div class="notice">${icon('shield')}<p>This expert has an approved verification application. Approval does not replace repository-specific access or review scope.</p></div>${can('assign_reviewer')?btn('Select for a review','hire-expert','primary',`data-id="${e(x.id)}"`):goto('View reviews','reviews')}`);};
  A.actions['review-access']=el=>accessModal(el,'platform');A.actions['expert-access']=el=>accessModal(el,'reviewer');
  function accessModal(el,target){if(!can('request_repository_access'))return A.toast('The code submitter manages repository access.');const id=el.dataset.id||A.state.activeReview;A.modal('Repository access request','Access is verified by the backend integration.',`<p class="muted">Request ${target==='platform'?'platform':'selected reviewer'} access for this review. An email address alone does not grant GitHub permissions. If GitHub is not configured, the API will report that the request cannot be completed.</p><form data-form="request-access"><input type="hidden" name="reviewId" value="${e(id)}"><input type="hidden" name="target" value="${target}">${err}<div class="card-actions">${submit('Request access')}</div></form>`);}
  A.forms['request-access']=async form=>pending(form,async()=>{requirePermission('request_repository_access');const d=data(form);const response=await post(`/reviews/${encodeURIComponent(d.reviewId)}/access-request`,{target:d.target});await refreshReview(d.reviewId);A.closeModal();A.go('review');A.modal('Access request recorded','Repository permission remains a separate step.',`<div class="kv"><span>Recipient</span><strong>${e(response.recipient||'Not configured')}</strong></div><div class="kv"><span>Status</span>${A.tag(response.status||'pending','amber')}</div><div class="notice">${e(response.message||'This request does not grant or verify GitHub access.')}</div>${response.recipient?btn('Copy recipient','flow-copy-email','secondary',`data-email="${e(response.recipient)}"`):''}`);});
  A.forms['send-message']=async form=>pending(form,async()=>{requirePermission('send_review_messages');const d=data(form);await post(`/reviews/${encodeURIComponent(d.reviewId)}/messages`,{text:String(d.message||'').trim()});const result=await request(`/reviews/${encodeURIComponent(d.reviewId)}/messages`);const r=A.state.reviews.find(x=>x.id===d.reviewId);if(r)r.messages=list(result,'messages');A.render();});
  A.actions['message-thread']=async el=>{try{requirePermission('read_review_messages');await refreshReview(el.dataset.id);const response=await request(`/reviews/${encodeURIComponent(el.dataset.id)}/messages`);A.state.reviews.find(x=>x.id===el.dataset.id).messages=list(response,'messages');A.render();}catch(error){A.toast(error.message);}};
  A.actions['open-review']=async el=>{try{await refreshReview(el.dataset.id);A.context.detailTab='scope';A.go('review');}catch(error){A.toast(error.message);}};
  for(const route of new Set(Object.values(allowedRoutes).flatMap(routes=>[...routes]))){
    const view=A.views[route];if(!view)continue;
    A.views[route]=()=>{
      if(!A.authenticated||!allowedRoutes[serverRole]?.has(route))return '<div class="notice amber" role="alert">This workspace is not available to your account.</div>';
      const verification=serverRole==='coder'?` · ${A.state.application?.status==='approved'?'approved reviewer':'verification required'}`:'';
      const roleBadge=`<div class="live-account-role" style="margin-bottom:16px" aria-label="Authenticated account role">${A.tag(roleLabels[serverRole]+verification)}</div>`;
      const notice=route==='overview'&&A.context.routeNotice?`<div class="notice amber" role="alert">${e(A.context.routeNotice)}</div>`:'';
      return roleBadge+notice+view();
    };
  }
  const originalRender=A.render;
  A.render=()=>{
    const route=location.hash.slice(1)||'overview';
    if(!A.authenticated&&!['home','register','otp'].includes(route)){location.hash='register';return;}
    if(A.authenticated){
      A.state.role=serverRole;
      if(!allowedRoutes[serverRole]?.has(route)){
        A.closeModal();if(!['home','register','otp'].includes(route))A.context.routeNotice='Your account cannot access that workspace.';
        location.hash='overview';return;
      }
    }
    originalRender();
    document.querySelectorAll('[data-change="role"],[data-action="reset-demo"],[data-action="google-demo"],[data-action="demo-dashboard"],[data-action="confirm-demo-access"]').forEach(el=>{el.disabled=true;el.hidden=true;});
    document.querySelectorAll('[data-action="finding-status"],[data-action="apply-review"],[data-action="billing-info"],[data-form="save-settings"] button[type="submit"]').forEach(el=>{el.disabled=true;el.title='Backend service not connected';});
    if(!can('create_review'))document.querySelectorAll('[data-route="new-review"]').forEach(el=>{el.hidden=true;el.disabled=true;});
    if(!can('assign_reviewer'))document.querySelectorAll('[data-action="hire-expert"],[data-form="confirm-hire"],[data-route="experts"]').forEach(el=>{el.hidden=true;el.disabled=true;});
    if(!can('request_repository_access'))document.querySelectorAll('[data-action="review-access"],[data-action="expert-access"],[data-form="request-access"],[data-route="repositories"]').forEach(el=>{el.hidden=true;el.disabled=true;});
    if(!can('send_review_messages'))document.querySelectorAll('[data-form="send-message"] input,[data-form="send-message"] button').forEach(el=>{el.disabled=true;el.title='Your account requires approved review access to send messages.';});
    if(serverRole==='coder'&&route==='review'){
      const accessPanel=document.querySelector('.detail-side > .panel:first-child');
      if(accessPanel)accessPanel.innerHTML='<div class="panel-head"><h2>Repository access</h2></div><div class="side-content"><p class="muted">The code submitter manages platform and reviewer access. You can review your assigned scope and discuss findings in this workspace.</p></div>';
    }
    const file=document.querySelector('[name="evidence"]');if(file){file.disabled=true;}
  };
  async function initialize(){
    A.apiLoading=true;A.apiError='';A.render();
    try {A.apiConfig=await request('/config');const catalog=A.apiConfig.task_categories;if(catalog && (!Array.isArray(catalog)||catalog.length!==A.categories.length||catalog.some(x=>!A.categories.some(c=>c.id===x.id&&c.label===x.label))))throw new Error('The API task category catalog does not match this frontend version.');try{await hydrate();}catch(error){if(error.status!==401)throw error;reset();A.authenticated=false;} }
    catch(error){A.apiError=error.message;reset();A.authenticated=false;}
    finally{A.apiLoading=false;if(A.authenticated&&['register','otp'].includes(location.hash.slice(1)))A.go(A.state.role==='team'?'team':'overview');A.render();}
  }
  A.actions['api-retry']=()=>initialize();
  A.api={request,hydrate,refreshReview,base,ready:initialize()};
})();
