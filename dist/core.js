/* Prototype-only browser state. This is not an authentication or authorization system. */
(() => {
const key = 'antislop-ui-v1';
const seed = () => {const result = {
  version: 1, role: 'submitter', user: {name:'Alex Morgan',email:'alex@example.com'}, activeReview:'r1',
  application: null,
  experts: [
    {id:'e1',name:'Sarah Chen',initials:'SC',title:'Application security engineer',skills:['TypeScript','Authorization','Node.js'],bio:'Reviews authorization boundaries and application security in modern SaaS products.',rate:85,verified:true,github:'sarah-chen-demo',email:'sarah@example.com',color:'peach'},
    {id:'e2',name:'Daniel Brooks',initials:'DB',title:'Senior backend engineer',skills:['Python','PostgreSQL','APIs'],bio:'Focuses on API correctness, data integrity, and failures that are difficult to reproduce.',rate:75,verified:true,github:'daniel-brooks-demo',email:'daniel@example.com',color:'blue'},
    {id:'e3',name:'Priya Nair',initials:'PN',title:'Full-stack code reviewer',skills:['React','TypeScript','Testing'],bio:'Turns complex front-end changes into specific, testable findings and clear remediation.',rate:65,verified:true,github:'priya-nair-demo',email:'priya@example.com',color:'purple'},
    {id:'e4',name:'Marcus Reed',initials:'MR',title:'Cloud and platform engineer',skills:['Go','Infrastructure','Security'],bio:'Reviews service boundaries, operational behavior, and infrastructure configuration.',rate:90,verified:true,github:'marcus-reed-demo',email:'marcus@example.com',color:''},
    {id:'e5',name:'Elena Torres',initials:'ET',title:'Quality and reliability specialist',skills:['Python','Testing','APIs'],bio:'Builds regression cases and checks how applications behave when dependencies fail.',rate:70,verified:true,github:'elena-torres-demo',email:'elena@example.com',color:'peach'},
    {id:'e6',name:'James Wilson',initials:'JW',title:'Payment systems reviewer',skills:['TypeScript','Payments','PostgreSQL'],bio:'Reviews idempotency, transaction boundaries, and payment lifecycle logic.',rate:95,verified:true,github:'james-wilson-demo',email:'james@example.com',color:'blue'}
  ],
  reviews: [
    {id:'r1',title:'Authentication service',repo:'https://github.com/example/auth-service',sha:'9f2a6b1',stack:'TypeScript',status:'Expert review',scope:'Check authorization and session boundaries. Confirm tenant isolation and test expiry behavior.',budget:650,deadline:'2026-10-18',access:'demo_confirmed',expertId:'e1',expertAccess:'pending',findings:[{id:'f1',title:'Tenant boundary is missing on resource lookup',severity:'High',file:'src/api/resources.ts:42',description:'Illustrative finding: resource lookup does not include the requesting tenant. A cross-tenant request could return another tenant’s record.',status:'Open'},{id:'f2',title:'Expired sessions are accepted by the refresh handler',severity:'Medium',file:'src/auth/refresh.ts:28',description:'Illustrative finding: the refresh path does not independently validate the session expiry. Add an expiry regression case.',status:'Open'}],proposals:[{id:'p1',expertId:'e1',message:'I can review tenant access, refresh behavior, and provide regression tests for confirmed findings.',amount:650},{id:'p2',expertId:'e3',message:'I’ll review the client/server auth boundaries and edge cases.',amount:550}],messages:[{id:'m1',from:'Sarah Chen',text:'I’ve reviewed the scope. Please confirm repository access before I begin the expert review.',time:'Sample conversation'}]},
    {id:'r2',title:'Checkout API',repo:'https://github.com/example/checkout-api',sha:'b4e7c92',stack:'Python',status:'AI reviewed',scope:'Review retry behavior and duplicate payment requests. Look for missing idempotency checks.',budget:800,deadline:'2026-10-21',access:'demo_confirmed',expertId:null,expertAccess:'pending',findings:[{id:'f3',title:'Repeated requests may create duplicate orders',severity:'High',file:'checkout/orders.py:63',description:'Illustrative finding: creating an order does not check an idempotency key. Reproduce with two requests using the same key.',status:'Open'}],proposals:[],messages:[]},
    {id:'r3',title:'Analytics dashboard',repo:'https://github.com/example/analytics-dashboard',sha:'c8d19a3',stack:'React',status:'Completed',scope:'Review dashboard filters and data export permissions.',budget:450,deadline:'2026-10-12',access:'demo_confirmed',expertId:'e3',expertAccess:'demo_confirmed',findings:[{id:'f4',title:'Export includes hidden columns',severity:'Medium',file:'src/export.ts:18',description:'Illustrative finding: data export did not apply the active column permissions. The demo issue has been marked verified.',status:'Verified'}],proposals:[],messages:[]},
    {id:'r4',title:'Notification worker',repo:'https://github.com/example/notification-worker',sha:'a63f214',stack:'Node.js',status:'Awaiting access',scope:'Check retry limits, duplicate delivery, and handling of invalid recipients.',budget:400,deadline:'2026-10-24',access:'pending',expertId:null,expertAccess:'pending',findings:[],proposals:[],messages:[]}
  ],
  applications: [
    {id:'v1',name:'Jamie Patel',email:'jamie@example.com',github:'jamie-patel-demo',experience:'5–8 years',specialty:'Application security',portfolio:'https://example.com/jamie',bio:'Sample application: backend developer with experience reviewing multi-tenant applications.',status:'pending'},
    {id:'v2',name:'Robin Ellis',email:'robin@example.com',github:'robin-ellis-demo',experience:'3–5 years',specialty:'Backend and APIs',portfolio:'https://example.com/robin',bio:'Sample application: API developer focused on test-driven development and reliability.',status:'pending'}
  ],
  events:[{text:'Sarah Chen was selected for Authentication service',time:'Sample activity · 12 min ago',icon:'users'},{text:'AI review ready for Checkout API',time:'Sample activity · 45 min ago',icon:'shield'},{text:'Analytics dashboard review completed',time:'Sample activity · 2 hours ago',icon:'check'}]
};result.reviews.forEach((review,index)=>{review.category=['security','backend-api','frontend-ux','devops-cloud'][index];});return result;};
let state;
try {const saved = JSON.parse(localStorage.getItem(key));state = saved?.version === 1 ? saved : seed();} catch {state=seed();}
const paths = {
grid:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',folder:'M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',shield:'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zM8 12l3 3 5-6',users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M16 4a4 4 0 0 1 0 7M22 21v-2a4 4 0 0 0-3-4',git:'M8 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4M8 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4M18 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4M8 8v9M18 8v3c0 4-10 0-10 6',code:'m8 5-6 7 6 7M16 5l6 7-6 7M14 3l-4 18',arrow:'M4 12h16M14 6l6 6-6 6',plus:'M12 5v14M5 12h14',search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14M15 15l6 6',bell:'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',chevron:'m8 10 4 4 4-4',check:'m5 12 4 4L19 6',clock:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M12 6v6l4 2',file:'M14 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9zM14 2v7h7M7 13h10M7 17h7',lock:'M6 10V7a6 6 0 0 1 12 0v3M4 10h16v11H4zM12 14v3',message:'M21 11a9 9 0 0 1-9 9H4l-3 2 2-6A9 9 0 1 1 21 11zM7 10h10M7 14h6',wallet:'M3 6h16v14H3zM3 6V3h14v3M16 11h5v5h-5z',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',help:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 4M12 17h.01',logout:'M9 4H3v16h6M9 12h12M16 7l5 5-5 5',link:'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2',star:'m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',download:'M12 3v12M7 10l5 5 5-5M4 16v5h16v-5',close:'M6 6l12 12M6 18 18 6',external:'M14 3h7v7M10 14 21 3M10 3H3v18h18v-7',briefcase:'M3 7h18v14H3zM8 7V3h8v4M3 12h18M10 12v3h4v-3',chart:'M3 3v18h18M7 16v-4M12 16V7M17 16v-6',mail:'M3 5h18v14H3zM3 5l9 8 9-8',copy:'M8 8h13v13H8zM16 8V3H3v13h5',send:'m3 3 19 9-19 9 4-9zM7 12h15'
};
const A = window.A = {state,context:{},views:{},actions:{},forms:{},inputs:{},route:'overview'};
A.categories = Object.freeze([
  {id:'security',label:'Security'},
  {id:'frontend-ux',label:'Frontend & UX'},
  {id:'backend-api',label:'Backend & APIs'},
  {id:'performance',label:'Performance'},
  {id:'testing-qa',label:'Testing & QA'},
  {id:'devops-cloud',label:'DevOps & Cloud'},
  {id:'data-ai',label:'Data & AI'},
  {id:'architecture',label:'Architecture & Refactoring'},
  {id:'general',label:'General review'}
].map(Object.freeze));
A.category = id => A.categories.find(category=>category.id===id) || A.categories.find(category=>category.id==='general');
A.state.reviews.forEach(review=>{review.category=A.category(review.category).id;});
A.esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
A.icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
A.tag = (text,color='green') => `<span class="tag ${A.esc(color)}"><i class="dot"></i>${A.esc(text)}</span>`;
A.categoryBadge = review => {const category=A.category(review.category);return `<span class="task-category" data-category="${A.esc(category.id)}">${A.esc(category.label)}</span>`;};
A.btn = (text,action,kind='primary',attrs='') => {
  const submit = /type=["']submit["']/.test(attrs);
  const clean = attrs.replace(/type=["'](?:submit|button)["']/g,'');
  return `<button type="${submit?'submit':'button'}" class="btn ${A.esc(kind)}" data-action="${A.esc(action)}" ${clean}>${text}</button>`;
};
A.avatar = (initials,color='') => `<span class="avatar ${A.esc(color)}">${A.esc(initials)}</span>`;
A.persist = () => {try {localStorage.setItem(key,JSON.stringify(A.state));} catch {A.toast('Browser storage is unavailable. Changes will last for this session only.');}};
A.go = route => {A.closeModal();if(location.hash===`#${route}`)A.render();else location.hash=route;};
let toastTimer;
A.toast = text => {const box=document.querySelector('#toast');box.textContent=text;box.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>box.classList.remove('show'),4500);};
let priorFocus;
A.modal = (title,subtitle,body,options={}) => {
  priorFocus = document.activeElement;
  document.querySelector('#modal-root').innerHTML = `<div class="modal-backdrop"><section class="modal ${options.large?'large':''}" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div class="modal-head"><div><h2 id="dialog-title">${A.esc(title)}</h2><p>${A.esc(subtitle)}</p></div><button class="icon-btn" data-action="close-modal" aria-label="Close dialog">${A.icon('close')}</button></div>${body}</section></div>`;
  document.querySelector('.modal button, .modal input, .modal select')?.focus();
};
A.closeModal = () => {const root=document.querySelector('#modal-root');if(root.innerHTML){root.innerHTML='';priorFocus?.isConnected && priorFocus.focus();}};
A.addEvent = (text,icon='check') => {A.state.events.unshift({text,time:'Just now · prototype',icon});A.state.events=A.state.events.slice(0,12);};
A.getReview = () => A.state.reviews.find(r=>r.id===A.state.activeReview) || A.state.reviews[0];
A.actions['close-modal']=A.closeModal;
A.actions['copy-email']=async el => {const value=el.dataset.email || 'antislop@bee3.in';try{await navigator.clipboard.writeText(value);A.toast('Email address copied');}catch{A.modal('Copy email address','Copy this address manually.',`<input readonly value="${A.esc(value)}" aria-label="Email address">`);}};
A.actions['reset-demo']=()=>A.modal('Reset the prototype?','This removes the demo changes saved in this browser.',`<p class="muted">Sample reviews and applications will be restored. No live account or repository is affected.</p><div class="form-actions">${A.btn('Cancel','close-modal','secondary')}${A.btn('Reset demo','confirm-reset')}</div>`);
A.actions['confirm-reset']=()=>{A.state=seed();A.persist();A.closeModal();Object.keys(A.context).forEach(k=>delete A.context[k]);A.go('overview');A.toast('Demo data restored');};
document.addEventListener('keydown',event=>{
 const modal=document.querySelector('.modal');if(!modal)return;
 if(event.key==='Escape'){event.preventDefault();A.closeModal();}
 if(event.key==='Tab'){
   const elements=[...modal.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]')];
   if(!elements.length)return;const first=elements[0],last=elements.at(-1);
   if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
 }
});
})();
