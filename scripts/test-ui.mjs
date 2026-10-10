import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const results=[];
const storage=new Map();
const scripts=['core.js','dashboards.js','flows.js','app.js'];
function boot(){
  const nodes=new Map();
  function node(){return {innerHTML:'',textContent:'',classList:{add(){},remove(){},toggle(){}},focus(){},isConnected:true};}
  for(const key of ['#app','#modal-root','#toast','#flow-error'])nodes.set(key,node());
  const listeners={};
  const doc={activeElement:null,title:'',querySelector:key=>nodes.get(key)||null,querySelectorAll:()=>[],getElementById:key=>nodes.get('#'+key)||null,addEventListener:(name,fn)=>(listeners[name]||=[]).push(fn)};
  class Data{constructor(form){this.data=form.data;}get(key){return this.data[key]??null;}entries(){return Object.entries(this.data)[Symbol.iterator]();}}
  const ctx={console,URL,FormData:Data,document:doc,location:{hash:''},navigator:{clipboard:{writeText:async()=>{}}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},setTimeout:()=>0,clearTimeout(){},window:{addEventListener(){},scrollTo(){}}};
  vm.createContext(ctx);
  for(const file of scripts)vm.runInContext(readFileSync(new URL('../dist/'+file,import.meta.url),'utf8'),ctx,{filename:file});
  return {A:ctx.window.A,ctx,nodes,listeners};
}
const runtime=boot();
const {A,ctx,nodes,listeners}=runtime;
const form=data=>({data,querySelector:()=>null});
const el=data=>({dataset:data});
const test=(name,fn)=>{try{fn();results.push({name,pass:true});}catch(error){results.push({name,pass:false,error:error.message});}};
test('All registered routes render without exceptions',()=>{
 for(const role of ['submitter','coder','team']){A.state.role=role;for(const route of Object.keys(A.views)){ctx.location.hash='#'+route;A.render();assert.ok(nodes.get('#app').innerHTML.length>100);}}
});
test('All rendered interactive actions exist',()=>{
 const missing=[];
 for(const route of Object.keys(A.views)){ctx.location.hash='#'+route;A.render();for(const match of nodes.get('#app').innerHTML.matchAll(/data-action="([^"]+)"/g)){if(match[1]&&!A.actions[match[1]])missing.push(route+': '+match[1]);}}
 assert.deepEqual([...new Set(missing)],[]);
});
test('Submit helper emits exactly one submit type',()=>{
 const button=A.btn('Save','','primary','type="submit"');
 assert.equal((button.match(/type=/g)||[]).length,1);
 assert.match(button,/type="submit"/);
});
test('OTP rejects wrong code and creates coder profile with demo code',()=>{
 A.context.authRole='coder';A.forms.register(form({name:'Jordan Reviewer',email:'jordan@example.com',demoConsent:'on'}));
 const oldName=A.state.user.name;
 A.forms.otp(form({otp:'111111'}));assert.equal(A.state.user.name,oldName);
 A.forms.otp(form({otp:'482913'}));assert.equal(A.state.user.name,'Jordan Reviewer');assert.equal(A.state.role,'coder');assert.equal(ctx.location.hash,'verification');
});
test('Unapproved coder cannot submit proposal',()=>{
 const before=A.state.reviews[1].proposals.length;
 A.forms['submit-proposal'](form({reviewId:'r2',message:'I will test the authorization boundaries.',amount:'500'}));
 assert.equal(A.state.reviews[1].proposals.length,before);
});
test('Application requires valid GitHub profile and separate team approval',()=>{
 const application={name:'Jordan Reviewer',email:'jordan@example.com',github:'https://evil.example/jordan',experience:'3–5 years',specialty:'Application security',portfolio:'https://example.com/jordan',bio:'I review multi-tenant applications and author regression cases.',consent:'on'};
 A.forms.verification(form(application));assert.equal(A.state.application,null);
 application.github='https://github.com/jordan-reviewer';A.forms.verification(form(application));assert.equal(A.state.application.status,'pending');
 A.actions['team-review'](el({id:A.state.application.id}));
 A.forms['team-decision'](form({decision:'changes_requested',notes:''}));assert.equal(A.state.application.status,'pending');
 A.forms['team-decision'](form({decision:'approved',notes:'Evidence reviewed in demo.'}));assert.equal(A.state.application.status,'approved');
});
test('Approved new coder can propose and submitter can finalize doer',()=>{
 const r=A.state.reviews.find(x=>x.id==='r2'),before=r.proposals.length;
 A.state.role='coder';A.forms['submit-proposal'](form({reviewId:r.id,message:'I will reproduce payment retries and build idempotency regression tests.',amount:'500'}));
 assert.equal(r.proposals.length,before+1);
 const p=r.proposals.at(-1);A.state.role='submitter';A.forms['confirm-hire'](form({reviewId:r.id,expertId:p.expertId}));
 assert.equal(r.expertId,p.expertId);assert.equal(r.expertAccess,'pending');
});
test('Review wizard validates URL, SHA, budget and creates only a local pending review',()=>{
 A.context.reviewStep=1;A.context.reviewDraft=null;
 A.forms['review-wizard'](form({title:'Tenant check',repo:'https://github.com.evil.example/org/repo',revisionType:'commit',revision:'abcdef1',stack:'TypeScript / Node.js',visibility:'private'}));assert.equal(A.context.reviewStep,1);
 A.forms['review-wizard'](form({title:'Tenant check',repo:'https://github.com/org/repo.git',revisionType:'commit',revision:'abcdef1',stack:'TypeScript / Node.js',visibility:'private'}));assert.equal(A.context.reviewStep,2);
 A.forms['review-wizard'](form({scope:'Tenant isolation and permission checks.',budget:'-1',deadline:'2026-10-21'}));assert.equal(A.context.reviewStep,2);
 A.forms['review-wizard'](form({scope:'Tenant isolation and permission checks.',budget:'500',deadline:'2026-10-21'}));assert.equal(A.context.reviewStep,3);
 const count=A.state.reviews.length;A.forms['review-wizard'](form({authorized:'on'}));assert.equal(A.state.reviews.length,count+1);
 const r=A.state.reviews[0];assert.equal(r.repo,'https://github.com/org/repo');assert.equal(r.access,'pending');assert.equal(r.findings.length,0);assert.equal(r.expertId,null);
});
test('AI and doer access acknowledgements stay independent and explicit demo states',()=>{
 const r=A.state.reviews[0];A.actions['expert-access'](el({id:r.id}));assert.equal(r.expertAccess,'pending');
 A.actions['review-access'](el({id:r.id}));assert.match(nodes.get('#modal-root').innerHTML,/antislop@bee3.in/);assert.match(nodes.get('#modal-root').innerHTML,/does not grant GitHub permissions/);
 A.actions['confirm-demo-access']();assert.equal(r.access,'demo_confirmed');assert.equal(r.expertAccess,'pending');assert.equal(r.findings.length,0);
 A.state.role='submitter';A.forms['confirm-hire'](form({reviewId:r.id,expertId:'e1'}));A.actions['expert-access'](el({id:r.id}));A.actions['confirm-demo-access']();assert.equal(r.expertAccess,'demo_confirmed');
});
test('Mark remediated never marks independently verified',()=>{
 const r=A.state.reviews.find(x=>x.id==='r1'),f=r.findings[0];A.state.role='submitter';A.actions['finding-status'](el({id:f.id,review:r.id}));assert.equal(f.status,'remediated');
});
test('User supplied fields are escaped across views and dialogs',()=>{
 const payload='<img src=x onerror="alert(1)">';
 A.state.user.name=payload;const r=A.state.reviews[0];r.title=payload;r.scope=payload;r.messages.push({from:payload,text:payload,time:payload});r.findings.push({id:'xss',title:payload,severity:'High',description:payload,file:payload,status:'Open'});A.state.activeReview=r.id;
 A.state.application.name=payload;A.state.application.bio=payload;A.state.application.notes=payload;
 for(const route of Object.keys(A.views)){ctx.location.hash='#'+route;A.render();assert.ok(!nodes.get('#app').innerHTML.includes(payload),route+' contains raw input');}
 A.actions['team-review'](el({id:A.state.application.id}));assert.ok(!nodes.get('#modal-root').innerHTML.includes(payload));
});
test('Refresh restores locally saved state',()=>{A.persist();const fresh=boot();assert.equal(fresh.A.state.reviews.length,A.state.reviews.length);assert.equal(fresh.A.state.user.name,A.state.user.name);});
test('Role switch clears flow context in place and staff opens team dashboard',()=>{
 const original=A.context;A.context.reviewDraft={title:'Stale draft'};
 for(const listener of listeners.change||[])listener({target:{dataset:{change:'role'},value:'team'}});
 assert.equal(A.context,original);assert.equal(A.context.reviewDraft,undefined);assert.equal(ctx.location.hash,'team');
});
test('Reset clears drafts and restores seed reviews',()=>{A.context.reviewDraft={title:'Stale draft'};A.actions['confirm-reset']();assert.equal(A.state.reviews.length,4);assert.equal(A.context.reviewDraft,undefined);});
test('Fixed category catalog and legacy fallback are stable',()=>{
 assert.equal(A.categories.length,9);assert.equal(new Set(A.categories.map(x=>x.id)).size,9);
 assert.equal(A.category(undefined).id,'general');assert.equal(A.category('<script>').id,'general');
 assert.equal(A.state.reviews.find(x=>x.id==='r1').category,'security');
 assert.ok(A.categoryBadge({category:'frontend-ux'}).includes('Frontend &amp; UX'));
});
test('Category filtering composes with status and clearing retains other filters',()=>{
 A.state.role='submitter';A.context.reviewFilter='active';A.context.reviewSearch='';
 A.actions['filter-review-category'](el({category:'security'}));
 let html=A.views.reviews();assert.equal((html.match(/<tr data-review-category=/g)||[]).length,1);assert.ok(html.includes('<tr data-review-category="security"'));
 A.context.reviewSearch='checkout';html=A.views.reviews();assert.ok(html.includes('No reviews match these filters'));
 A.actions['clear-review-category']();assert.equal(A.context.reviewSearch,'checkout');assert.equal(A.context.reviewFilter,'active');
 html=A.views.reviews();assert.ok(html.includes('<tr data-review-category="backend-api"'));
 A.actions['filter-review-category'](el({category:'unknown'}));assert.equal(A.context.reviewCategory,'all');
});
console.log(JSON.stringify({passed:results.filter(x=>x.pass).length,total:results.length,results},null,2));
if(results.some(x=>!x.pass))process.exitCode=1;
