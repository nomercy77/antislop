(() => {
const A=window.A, {esc,icon,btn}=A;
const logo = () => `<button class="logo" data-action="go-home" aria-label="Antislop home"><span class="logo-mark"><svg viewBox="0 0 25 28" fill="none" aria-hidden="true"><path d="m4 23 8.5-19L21 23M7 18h11" stroke="currentColor" stroke-width="2.7" stroke-linecap="round"/></svg></span>antislop<span style="color:#92af76">.</span></button>`;
const art = () => `<div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="orbit two"></div><div class="code-float"><div class="dots"><i></i><i></i><i></i></div><div class="code-line"></div><div class="code-line"></div><div class="code-line"></div><div class="code-line"></div><div class="code-line"></div></div><div class="shield-float">${icon('shield')}</div><span class="spark">✧</span></div>`;
A.logo=logo;A.art=art;
const labels={overview:'Overview',reviews:'My reviews',experts:'Find experts',repositories:'Repositories',messages:'Messages',billing:'Billing',settings:'Settings',verification:'Coder verification',team:'Verification queue','new-review':'New review',review:'Review workspace',profile:'Expert profile'};
const navItem=(route,symbol,label,count='')=>`<button data-action="navigate" data-route="${route}" class="${A.route===route?'active':''}" ${A.route===route?'aria-current="page"':''}>${icon(symbol)}${label}${count?`<span class="count">${count}</span>`:''}</button>`;
const sidebar=()=>{
 const role=A.state.role;
 const name=role==='team'?'Verification team':role==='coder'?'Coder workspace':'Submitter workspace';
 return `<aside class="sidebar" id="sidebar">${logo()}<div class="workspace-pill">${A.avatar(role==='team'?'VT':role==='coder'?'JL':'AM')}<div><strong>${name}</strong><small>${A.live?'Authenticated workspace':'Personal · demo workspace'}</small></div>${icon('chevron')}</div><div class="nav-label">WORKSPACE</div><nav class="nav" aria-label="Main navigation">${navItem('overview','grid','Overview')}${role==='team'?navItem('team','shield','Verification queue',String(new Set([...A.state.applications,A.state.application].filter(x=>x?.status==='pending').map(x=>x.id)).size)):navItem('reviews','folder',role==='coder'?'Reviews & assignments':'My reviews',String(A.state.reviews.length))}${role==='coder'?navItem('verification','shield','My verification'):role==='submitter'?navItem('experts','users','Find experts'):''}${role==='submitter'?navItem('repositories','git','Repositories'):''}${role!=='team'?navItem('messages','message','Messages'):''}${role!=='team'?navItem('billing','wallet',role==='coder'?'Earnings':'Billing'):''}</nav><div class="sidebar-bottom"><div class="sidebar-tip"><div class="tip-icon">${icon('shield')}</div><h4>Good code deserves a second look.</h4><p>Bring evidence, expertise, and your next release into one workspace.</p><button class="text-btn" data-action="learn-workflow">Explore the workflow ${icon('arrow')}</button></div><nav class="nav" aria-label="Account navigation">${navItem('settings','settings','Settings')}<button data-action="help">${icon('help')}Help & resources</button></nav><div class="account">${A.avatar(role==='team'?'VT':(A.state.user.name||'Alex Morgan').split(' ').map(x=>x[0]).slice(0,2).join(''))}<div><strong>${esc(role==='team'?'Review operations':A.state.user.name)}</strong><small>${A.live?'Authenticated account':role==='team'?'Staff preview':role==='coder'?'Coder preview':'Submitter preview'}</small></div><button class="icon-btn" data-action="signout" aria-label="${A.live?'Sign out':'Leave demo account'}">${icon('logout')}</button></div></div></aside>`;
};
const topbar=()=>`<header class="topbar"><button class="mobile-menu icon-btn" data-action="mobile-menu" aria-label="Toggle navigation">${icon('grid')}</button><div class="breadcrumb">Workspace / <span>${esc(labels[A.route]||'Overview')}</span></div><div class="top-actions"><div class="top-search">${icon('search')}<input aria-label="Search reviews" placeholder="Search your workspace" data-input="global-search"><kbd>⌘ K</kbd></div>${A.live?'':`<select class="role-switch" aria-label="Choose prototype role" data-change="role"><option value="submitter" ${A.state.role==='submitter'?'selected':''}>Preview: Submitter</option><option value="coder" ${A.state.role==='coder'?'selected':''}>Preview: Coder</option><option value="team" ${A.state.role==='team'?'selected':''}>Preview: Verification team</option></select>`}<button class="icon-btn" data-action="notifications" aria-label="View notifications">${icon('bell')}<i class="notification-dot"></i></button>${A.avatar((A.state.user.name||'Account').split(' ').map(x=>x[0]).slice(0,2).join(''))}</div></header>`;
const demoStrip=()=>`<div class="demo-strip">${icon('code')}<span>Interactive prototype · sample data</span><span class="optional">· No live emails, scans, payments, or GitHub grants</span><button data-action="register">Try registration</button><button data-action="reset-demo">Reset demo</button></div>`;
A.views.home=()=>`<div class="landing"><header class="landing-nav">${logo()}<div class="landing-links"><button data-action="learn-workflow">How it works</button><button data-action="explore-experts">Find a coder</button>${btn('Log in','register','secondary')}${btn('Get started','register')}</div></header><section class="landing-hero"><div><div class="eyebrow">A second look. A stronger release.</div><h1>Ship with confidence.<br><em>Not crossed fingers.</em></h1><p>A workspace for automated code review, verified coders, and the evidence behind every fix.</p><div class="heading-actions">${btn('Submit code for review '+icon('arrow'),'register')}${btn('Explore the demo','demo-dashboard','secondary')}</div><p style="font-size:11px;margin-top:18px">Built for code submitters. Backed by skilled reviewers.</p></div><div class="landing-art-wrap">${art()}<div class="landing-art-label">${icon('shield')}From finding to verified fix.</div></div></section><section class="landing-flow"><article><span class="tag">01 / SUBMIT</span><h3>Bring your repository.</h3><p>Define the scope, pin the commit, and follow the access setup in your workspace.</p></article><article><span class="tag">02 / REVIEW</span><h3>Give your code a second look.</h3><p>Explore automated findings and choose a verified coder for deeper review.</p></article><article><span class="tag">03 / VERIFY</span><h3>Close the loop.</h3><p>Discuss findings, track remediation, and keep the evidence alongside every decision.</p></article></section></div>`;
A.render=()=>{
 const route=location.hash.replace(/^#/,'')||'overview';
 A.route=A.views[route]?route:'overview';
 const standalone=['home','register','otp'].includes(A.route);
 const content=A.views[A.route]?.()||'<div class="empty">This workspace is loading.</div>';
 document.querySelector('#app').innerHTML=(A.live?'<div class="demo-strip"><span>FastAPI workspace · GitHub integration, AI scans, and payments are not connected</span></div>':demoStrip())+(standalone?content:`<div class="layout">${sidebar()}<div class="shell">${topbar()}<main class="main" id="main">${content}<footer class="page-footer"><span>${icon('lock')}${A.live?'Account data is stored by the API.':'Prototype data stays in this browser.'}</span><span>Made for thoughtful releases. © 2026 Antislop</span></footer></main></div></div>`);
 document.title=`${A.route==='home'?'Antislop':labels[A.route]||'Antislop'} — Antislop`;
 document.querySelectorAll('.table-scroll').forEach(el=>{el.tabIndex=0;el.setAttribute('role','region');el.setAttribute('aria-label','Scrollable reviews table');});
};
Object.assign(A.actions,{
 navigate:el=>A.go(el.dataset.route),
 go:el=>A.go(el.dataset.route==='landing'?'home':el.dataset.route),
 'go-home':()=>A.go('home'),
 register:()=>A.go('register'),
 'demo-dashboard':()=>A.go('overview'),
 'explore-experts':()=>{A.state.role='submitter';A.persist();A.go('experts');},
 'mobile-menu':()=>document.querySelector('#sidebar')?.classList.toggle('open'),
 signout:()=>{Object.keys(A.context).forEach(k=>delete A.context[k]);A.go('register');A.toast('You left the demo workspace. No live sign-in session was active.');},
 notifications:()=>A.modal('Workspace activity','Illustrative activity and your actions in this prototype.',`<div class="activity">${A.state.events.map(e=>`<div class="activity-item"><span class="activity-icon">${icon(e.icon)}</span><div><p>${esc(e.text)}</p><small>${esc(e.time)}</small></div></div>`).join('')}</div>`),
 help:()=>A.modal('How can we help?','Antislop prototype guide',`<div class="notice">${icon('mail')}<div>Platform review contact: <strong>antislop@bee3.in</strong><br>Access status is simulated here. This prototype sends no emails.</div></div><p class="muted">Use the preview selector to explore submitter, coder, and verification team workspaces. Try submitting a review, applying for coder verification, and reviewing an application.</p><div class="form-actions">${btn('Close','close-modal','secondary')}${btn('Try registration','register')}</div>`),
 'learn-workflow':()=>A.modal('One workspace. Three perspectives.','Explore the complete journey.',`<div class="access-step"><span class="number">1</span><div><h4>Submitter</h4><p>Submit a repository and review brief. Follow platform access setup, view demo findings, and select a coder.</p></div></div><div class="access-step"><span class="number">2</span><div><h4>Coder</h4><p>Submit a verification application. Once approved in the team preview, apply for work and submit structured findings.</p></div></div><div class="access-step"><span class="number">3</span><div><h4>Verification team</h4><p>Review coder applications and simulate approval or request changes. Production staff permissions will be enforced by the backend.</p></div></div><div class="form-actions">${btn('Close','close-modal','secondary')}${btn('Start registration','register')}</div>`)
});
A.inputs['global-search']=(value)=>{A.context.reviewSearch=value;};
document.addEventListener('click',async event=>{
 const el=event.target.closest('[data-action]');if(!el||el.disabled)return;
 const action=A.actions[el.dataset.action];if(!action)return;
 try {await action(el,event);}catch(error){console.error(error);A.toast('Something went wrong in the prototype. Please try again.');}
});
document.addEventListener('submit',async event=>{
 const form=event.target.closest('form[data-form]');if(!form)return;event.preventDefault();if(!form.reportValidity())return;
 const handler=A.forms[form.dataset.form];if(handler){try{await handler(form,event);}catch(error){console.error(error);A.toast('The form could not be saved. Please check the details.');}}
});
document.addEventListener('input',event=>{const el=event.target;if(el.dataset.input && A.inputs[el.dataset.input])A.inputs[el.dataset.input](el.value,el);});
document.addEventListener('change',event=>{
 const el=event.target;
 if(el.dataset.change==='role' && !A.live){
   A.state.role=el.value;A.persist();Object.keys(A.context).forEach(k=>delete A.context[k]);A.go(el.value==='team'?'team':'overview');
 }else if(el.dataset.input && A.inputs[el.dataset.input])A.inputs[el.dataset.input](el.value,el);
});
document.addEventListener('keydown',event=>{if(event.key==='Enter' && event.target.dataset.input==='global-search'){event.preventDefault();A.go('reviews');}});
window.addEventListener('hashchange',()=>{A.render();window.scrollTo(0,0);const heading=document.querySelector('h1');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}});
A.render();
})();
