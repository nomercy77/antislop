import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = fs.readFileSync(path.join(root, 'dist/api.js'), 'utf8');
const routeMap = {
  submitter: ['overview','reviews','experts','repositories','messages','billing','settings','new-review','review','profile'],
  coder: ['overview','reviews','verification','messages','billing','settings','review','profile'],
  team: ['overview','team','settings']
};
const allRoutes = [...new Set([...Object.values(routeMap).flat(), 'home', 'register', 'otp', 'unknown-route'])];
const results = [];
async function test(name, run) {
  try { await run(); results.push({ name, pass: true }); }
  catch (error) { results.push({ name, pass: false, error: error.message }); }
}

async function harness(role = 'submitter', { authenticated = true, approved = false, apiBaseUrl = 'http://127.0.0.1:8000' } = {}) {
  let hash = '#overview';
  const location = { get hash() { return hash; }, set hash(value) { hash = value.startsWith('#') ? value : '#' + value; }, assign: value => calls.push({ redirect: value }) };
  const calls = [], rendered = [], toasts = [];
  const permissions = {
    submitter: ['create_review','read_own_reviews','assign_reviewer','request_repository_access','read_review_messages','send_review_messages'],
    coder: ['apply_verification','read_own_reviews', ...(approved ? ['read_assigned_reviews','browse_opportunities','read_review_messages','send_review_messages'] : [])],
    team: ['read_verification_queue','decide_verification']
  }[role];
  const user = { id: 'u1', name: 'Authenticated member', email: 'member@example.com', role, permissions, verification_status: role === 'coder' ? approved ? 'approved' : 'pending' : null };
  const controls = { create: {}, assign: {}, access: {}, messages: {}, roleSelector: {}, reset: {} };
  const panel = { innerHTML: '' };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const A = {
    state: { reviews: [{ id:'fixture-review' }], role:'submitter', user:{ name:'Fixture user' } }, context:{}, actions:{}, forms:{}, inputs:{}, views:{}, categories:[],
    esc: escape, icon: () => '', tag: value => `<span>${escape(value)}</span>`, btn: (label, action, kind, attrs='') => `<button data-action="${action}" ${attrs}>${label}</button>`,
    category: () => ({ id:'general', label:'General review' }), categoryBadge: () => '<span>General review</span>',
    persist: () => {}, toast: text => toasts.push(text), closeModal: () => {}, modal: () => {}, go: route => { location.hash = route; }
  };
  for (const route of allRoutes.filter(x => x !== 'unknown-route')) A.views[route] = () => `<section>${route}</section>`;
  A.render = () => { const route = location.hash.slice(1); rendered.push({ route, html:A.views[route]?.() || '' }); };
  const document = {
    getElementById: () => null,
    querySelector: selector => selector.includes('detail-side') && location.hash === '#review' ? panel : null,
    querySelectorAll: selector => {
      if (selector.includes('[data-change="role"]')) return [controls.roleSelector, controls.reset];
      if (selector.includes('[data-route="new-review"]')) return [controls.create];
      if (selector.includes('[data-action="hire-expert"]')) return [controls.assign];
      if (selector.includes('[data-action="review-access"]')) return [controls.access];
      if (selector.includes('[data-form="send-message"] input')) return [controls.messages];
      return [];
    }
  };
  class FormDataMock {
    constructor(form) { this.values = form.values || {}; }
    entries() { return Object.entries(this.values)[Symbol.iterator](); }
  }
  const review = { id:'r1', title:'Private assigned review', repo:'https://github.com/example/private', sha:'a1b2c3d', stack:'Python', scope:'Review the important authorization workflows.', budget:100, deadline:'2026-10-20', visibility:'private', status:'Awaiting access', expertId:'u1', findings:[], proposals:[], messages:[] };
  const context = {
    window: { A, ANTISLOP_CONFIG:{ apiBaseUrl } }, console, URL, AbortController, setTimeout, clearTimeout, location, document, FormData:FormDataMock,
    fetch: async (url, options = {}) => {
      calls.push({ url, method:options.method || 'GET', body:options.body, credentials:options.credentials });
      let body = {}, status = 200;
      if (url.endsWith('/config')) body = { auth:{ email_otp:true, google:false } };
      else if (url.endsWith('/auth/me')) { body = authenticated ? { user } : { detail:'Authentication required' }; status = authenticated ? 200 : 401; }
      else if (url.endsWith('/coder/applications/me')) body = { application:{ id:'a1', status:approved ? 'approved' : 'pending' } };
      else if (url.endsWith('/staff/applications')) body = { applications:[] };
      else if (url.endsWith('/experts')) body = { experts:[] };
      else if (url.endsWith('/events')) body = { events:[] };
      else if (url.endsWith('/opportunities')) body = { opportunities:[] };
      else if (url.endsWith('/reviews')) body = { reviews:role === 'coder' && approved ? [review] : [] };
      else if (url.endsWith('/reviews/r1')) body = { review };
      else if (url.endsWith('/reviews/r1/messages')) body = options.method === 'POST' ? { message:{ id:'m1', text:'A message' } } : { messages:[] };
      else throw new Error('Unexpected API request: ' + url);
      return { ok:status >= 200 && status < 300, status, json:async () => body };
    }
  };
  vm.createContext(context); vm.runInContext(source, context, { filename:'api.js' });
  if (A.api) await A.api.ready;
  return { A, location, calls, rendered, controls, panel, toasts };
}

for (const role of ['submitter', 'coder', 'team']) {
  await test(`${role}: complete route authorization matrix`, async () => {
    const { A, location, rendered } = await harness(role);
    for (const route of allRoutes) {
      location.hash = route; const before = rendered.length; A.render();
      if (routeMap[role].includes(route)) assert.equal(rendered.length, before + 1, `Allowed route ${route}`);
      else { assert.equal(location.hash, '#overview', `Denied route ${route}`); assert.equal(rendered.length, before, `Unauthorized ${route} reached the renderer`); }
    }
  });
  await test(`${role}: server role, permissions, and badge resist local changes`, async () => {
    const { A, location } = await harness(role);
    A.state.role = role === 'team' ? 'submitter' : 'team'; location.hash = 'overview'; A.render();
    assert.equal(A.state.role, role);
    assert.match(A.views.overview(), /live-account-role/);
    A.actions['auth-role']({ dataset:{ role:'coder' } });
    assert.equal(A.context.authRole, undefined);
    if (role === 'coder') { A.state.user.permissions.push('create_review'); A.state.application.status = 'approved'; assert.equal(A.hasPermission('create_review'), false); assert.equal(A.hasPermission('send_review_messages'), false); }
    assert.match(A.views.register(), /cannot change an existing account/);
  });
}

await test('Unauthenticated users can render only home, registration, and OTP', async () => {
  const { A, location, rendered } = await harness('submitter', { authenticated:false });
  assert.equal(A.authenticated, false); assert.equal(A.state.reviews.length, 0);
  for (const route of allRoutes) {
    location.hash = route; const before = rendered.length; A.render();
    if (['home','register','otp'].includes(route)) assert.equal(rendered.length, before + 1);
    else { assert.equal(location.hash, '#register'); assert.equal(rendered.length, before); }
  }
  A.actions['auth-role']({ dataset:{ role:'coder' } }); assert.equal(A.context.authRole, 'coder'); assert.equal(A.state.role, 'submitter');
  A.actions['auth-role']({ dataset:{ role:'team' } }); assert.equal(A.context.authRole, 'coder');
  assert.doesNotMatch(A.views.otp(), /482913/);
});

await test('Pending coders have no private assignments and no submitter controls', async () => {
  const { A, location, controls, panel } = await harness('coder');
  assert.equal(A.state.reviews.length, 0); assert.equal(A.state.application.status, 'pending');
  location.hash='review'; A.render();
  for (const name of ['create','assign','access']) { assert.equal(controls[name].hidden, true); assert.equal(controls[name].disabled, true); }
  assert.equal(controls.messages.disabled, true); assert.match(panel.innerHTML, /submitter manages/);
  assert.equal(controls.roleSelector.hidden, true); assert.equal(controls.reset.hidden, true);
  assert.doesNotMatch(A.views['new-review'](), /data-form/); assert.doesNotMatch(A.views.team(), /data-form/);
});

await test('Approved coders retain permitted messaging but cannot assign or grant access', async () => {
  const { A, location, controls } = await harness('coder', { approved:true });
  assert.equal(A.state.reviews.length, 1); assert.equal(A.hasPermission('send_review_messages'), true);
  location.hash='review'; A.render(); assert.equal(controls.messages.disabled, undefined);
  assert.equal(controls.assign.hidden, true); assert.equal(controls.access.hidden, true);
});

function form(values = {}) { return { dataset:{}, values, querySelectorAll:() => [], querySelector:() => null }; }
await test('Denied mutation handlers make no network request', async () => {
  const { A, calls, toasts } = await harness('coder');
  const before=calls.length;
  for (const name of ['review-wizard','confirm-hire','request-access','team-decision','send-message']) await A.forms[name](form());
  A.actions['hire-expert']({ dataset:{ id:'e1' } }); A.actions['review-access']({ dataset:{ id:'r1' } });
  assert.equal(calls.length, before); assert.ok(toasts.some(text => text.includes('permission')));
});

await test('Team cannot invoke submitter or coder mutation handlers', async () => {
  const { A, calls } = await harness('team'); const before=calls.length;
  for (const name of ['review-wizard','verification','confirm-hire','request-access','send-message']) await A.forms[name](form());
  assert.equal(calls.length, before);
});

await test('Invalid configured API fails closed; blank configuration keeps prototype isolated', async () => {
  const invalid=await harness('submitter', { apiBaseUrl:'http://unsafe.example' });
  assert.equal(invalid.A.live, true); assert.equal(invalid.A.authenticated, false); assert.equal(invalid.A.state.reviews.length, 0); assert.equal(invalid.calls.length, 0);
  const demo=await harness('submitter', { apiBaseUrl:'' }); assert.equal(demo.A.live, undefined); assert.equal(demo.A.state.reviews[0].id, 'fixture-review');
});

await test('Authenticated API requests use cookie credentials', async () => {
  const { calls } = await harness('submitter'); assert.ok(calls.length > 0); assert.ok(calls.every(call => call.credentials === 'include'));
});

const passed = results.filter(result => result.pass).length;
console.log(JSON.stringify({ passed, total:results.length, results }, null, 2));
if (passed !== results.length) process.exitCode = 1;
