(() => {
  'use strict';
  const A = window.A;
  const e = A.esc;
  const i = A.icon;
  const b = A.btn;
  const t = A.tag;
  const categoryBadge = review => A.categoryBadge(review);
  const attr = (id) => `data-id="${e(id)}"`;
  const routeButton = (label, route, kind = 'secondary') => b(label, 'dashboard-go', kind, `data-route="${e(route)}"`);
  const money = (value) => '$' + Number(value || 0).toLocaleString('en-US');
  const reviews = () => A.state.reviews || [];
  const experts = () => A.state.experts || [];
  const currentReview = () => reviews().find(r => r.id === A.state.activeReview) || reviews()[0];
  const expertFor = (r) => experts().find(x => x.id === r.expertId);
  const approved = () => A.state.application?.status === 'approved';
  const statusTag = (status) => {
    const value = String(status || 'Draft');
    const color = /complete|verified|approved/i.test(value) ? 'green' : /pending|await|open|draft/i.test(value) ? 'amber' : 'blue';
    return t(value.replaceAll('_', ' '), color);
  };
  const heading = (title, subtitle, actions = '') => `<div class="page-heading"><div class="heading-copy"><div class="eyebrow">YOUR WORKSPACE</div><h1>${e(title)}</h1><p>${e(subtitle)}</p></div><div class="heading-actions">${actions}</div></div>`;
  const empty = (title, description, action = '') => `<div class="empty">${i('folder')}<h3>${e(title)}</h3><p>${e(description)}</p>${action ? `<div style="margin-top:18px">${action}</div>` : ''}</div>`;
  const stat = (label, value, foot, icon) => `<article class="stat"><div class="stat-top">${e(label)}${i(icon)}</div><div class="stat-value">${e(value)}</div><div class="stat-bottom">${e(foot)}</div></article>`;
  const heroArt = `<div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="orbit two"></div><div class="code-float"><div class="dots"><i></i><i></i><i></i></div><div class="code-line"></div><div class="code-line"></div><div class="code-line"></div><div class="code-line"></div></div><div class="shield-float">${i('shield')}</div><span class="spark">✦</span></div>`;
  const footer = '';

  function reviewTable(items, compact = false) {
    if (!items.length) return empty('No reviews here yet', 'Try another filter or create your first review.', routeButton('Start a review', 'new-review', 'primary'));
    return `<div class="table-scroll"><table><thead><tr><th>REPOSITORY / REVIEW</th><th>STATUS</th><th>${A.state.role === 'coder' ? 'BUDGET' : 'FINDINGS'}</th><th>REVIEWER</th><th></th></tr></thead><tbody>${items.map(r => {
      const expert = expertFor(r);
      return `<tr data-review-category="${e(A.category(r.category).id)}"><td><button class="repo-cell table-review-link" data-action="open-review" ${attr(r.id)}><span class="repo-icon">${i('git')}</span><span><strong>${e(r.title)}</strong><small>${e(r.repo.replace(/^https?:\/\/github.com\//, ''))} · ${e(r.stack || 'Code review')}</small><span class="repo-category">${categoryBadge(r)}</span></span></button></td><td>${statusTag(r.status)}</td><td>${A.state.role === 'coder' ? money(r.budget) : `<strong>${(r.findings || []).length}</strong> <small>sample findings</small>`}</td><td>${expert ? `<div class="repo-cell">${A.avatar(expert.initials, expert.color)}<span><strong>${e(expert.name)}</strong><small>Assigned expert</small></span></div>` : '<small>Not assigned</small>'}</td><td><button class="icon-btn" aria-label="Open ${e(r.title)}" data-action="open-review" ${attr(r.id)}>${i('arrow')}</button></td></tr>`;
    }).join('')}</tbody></table></div>${compact ? `<div class="table-footer"><span>${items.length} reviews in this preview</span><button class="text-btn" data-action="dashboard-go" data-route="reviews">View all reviews ${i('arrow')}</button></div>` : ''}`;
  }

  function activityPanel() {
    const events = (A.state.events || []).slice(0, 4);
    return `<section class="panel"><div class="panel-head"><h2>Recent activity</h2>${i('clock')}</div><div class="activity">${events.map(x => `<div class="activity-item"><span class="activity-icon">${i(x.icon || 'check')}</span><div><p>${e(x.text)}</p><small>${e(x.time || 'Just now')}</small></div></div>`).join('') || '<p class="muted">Your workspace activity will appear here.</p>'}</div></section>`;
  }

  function overview() {
    if (A.state.role === 'team') {
      const applications = A.state.applications || [];
      return `${heading('Verification workspace', 'A separate team reviews expert experience and profile evidence.', routeButton('Open verification queue', 'team', 'primary'))}<div class="stats">${stat('Pending applications', applications.filter(x => x.status === 'pending').length, 'Awaiting a team decision', 'clock')}${stat('Approved experts', applications.filter(x => x.status === 'approved').length, 'Demo approval records', 'shield')}${stat('Review workspaces', reviews().length, 'Illustrative workspace data', 'folder')}${stat('Platform access', reviews().filter(x => x.access === 'pending').length, 'Needs repository access', 'lock')}</div><section class="hero"><div><div class="eyebrow">QUALITY BEGINS WITH TRUST</div><h2>Meet the people behind the expertise.</h2><p>Review applications, check supporting experience, and record a clear verification decision before an expert can propose work.</p>${routeButton('Review applications →', 'team', 'primary')}</div>${heroArt}</section><div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2>Expert applications</h2><p>Local demo records · no external verification performed</p></div></div><div class="table-scroll"><table><thead><tr><th>APPLICANT</th><th>SPECIALTY</th><th>STATUS</th></tr></thead><tbody>${applications.map(x => `<tr><td><strong>${e(x.name)}</strong><br><small>${e(x.email)}</small></td><td>${e(x.specialty)}</td><td>${statusTag(x.status)}</td></tr>`).join('')}</tbody></table></div><div class="panel-bottom">${routeButton('Manage verification queue', 'team', 'secondary')}</div></section>${activityPanel()}</div>${footer}`;
    }
    const coder = A.state.role === 'coder';
    const name = (A.state.user?.name || 'Alex').split(' ')[0];
    const active = reviews().filter(r => !/complete|closed/i.test(r.status));
    const assigned = reviews().filter(r => r.expertId);
    const findingCount = reviews().reduce((n, r) => n + (r.findings || []).length, 0);
    const actions = coder ? routeButton('Browse opportunities', 'reviews', 'primary') : routeButton('+ New review', 'new-review', 'primary');
    return `${heading(`Good morning, ${name}`, coder ? 'Your next meaningful code review starts here.' : 'A clearer picture of your code. A calmer path to release.', actions)}
      <section class="hero"><div><div class="eyebrow">${coder ? 'BUILD TRUST. DO GREAT WORK.' : 'CONFIDENCE, BEFORE YOU SHIP.'}</div><h2>${coder ? 'Put your expertise where it makes a difference.' : 'Great code deserves a second set of eyes.'}</h2><p>${coder ? 'Find focused review engagements, collaborate with teams, and help turn findings into verified fixes.' : 'Bring your repository, define what matters, and connect with a verified expert for a focused review.'}</p>${coder ? routeButton(approved() ? 'Explore review opportunities →' : 'Complete expert verification →', approved() ? 'reviews' : 'verification', 'primary') : routeButton('Submit your first repository →', 'new-review', 'primary')}</div>${heroArt}</section>
      <div class="stats">${coder ? stat('Available engagements', active.length, 'Sample opportunities', 'briefcase') + stat('Assigned reviews', assigned.length, 'Preview assignments', 'folder') + stat('Verification', approved() ? 'Approved' : 'Pending', 'Separate team review required', 'shield') + stat('Earnings', '$0', 'Payments are not connected', 'wallet') : stat('Active reviews', active.length, 'Across your workspace', 'folder') + stat('Findings to review', findingCount, 'Illustrative sample findings', 'shield') + stat('Expert engagements', assigned.length, 'Curated expert support', 'users') + stat('Review budget', money(reviews().reduce((n, r) => n + Number(r.budget || 0), 0)), 'Proposed budget · no charges', 'wallet')}</div>
      <div class="dashboard-grid"><div><section class="panel"><div class="panel-head"><div><h2>${coder ? 'Review opportunities' : 'Your reviews'}</h2><p>${coder ? 'Well-scoped work for thoughtful reviewers' : 'Repository checks, expert reviews, and verified fixes'}</p></div><button class="text-btn" data-action="dashboard-go" data-route="reviews">View all ${i('arrow')}</button></div><div class="tabs"><button class="active">${coder ? 'Available work' : 'Recent reviews'} <span>${reviews().length}</span></button></div>${reviewTable(reviews().slice(0, 3), true)}</section>
      <section class="panel chart-panel"><div class="panel-head"><div><h2>A better review, one step at a time</h2><p>One shared workspace from submission to resolution</p></div>${t('Workflow preview')}</div><div class="journey"><div><span>01</span><strong>Set the scope</strong><p>Repository, commit, and risks.</p></div><div><span>02</span><strong>Review the evidence</strong><p>Checks and expert findings.</p></div><div><span>03</span><strong>Verify the fix</strong><p>Retest the affected commit.</p></div></div></section></div>
      <aside class="col-stack">${coder ? `<section class="panel"><div class="panel-head"><h2>Your expert profile</h2>${i('shield')}</div><div class="side-content"><div class="notice ${approved() ? '' : 'amber'}">${i('shield')}<p>${approved() ? 'Your demo profile is approved. You can explore the proposal workflow.' : 'Complete your profile to request verification. A separate team checks experience before approval.'}</p></div>${routeButton(approved() ? 'View verification' : 'Complete your profile', 'verification', 'soft')}</div></section>` : `<section class="panel"><div class="panel-head"><h2>Meet your next reviewer</h2>${i('users')}</div>${experts().slice(0, 3).map(x => `<div class="reviewer-item">${A.avatar(x.initials, x.color)}<div><strong>${e(x.name)}${x.verified ? i('shield') : ''}</strong><small>${e(x.title)}</small></div><div class="reviewer-price">${money(x.rate)}<small> / hr</small></div></div>`).join('')}<div class="panel-bottom">${routeButton('Explore experts', 'experts', 'secondary')}</div></section>`}${activityPanel()}</aside></div>${footer}`;
  }

  function reviewList() {
    const filter = A.context.reviewFilter || 'all';
    const query = (A.context.reviewSearch || '').toLowerCase();
    const selectedCategory = A.context.reviewCategory || 'all';
    const candidates = reviews().filter(r => {
      const statusMatch = filter === 'all' || (filter === 'active' ? !/complete|closed/i.test(r.status) : filter === 'completed' ? /complete|closed/i.test(r.status) : !r.expertId);
      return statusMatch && `${r.title} ${r.repo} ${r.stack} ${A.category(r.category).label}`.toLowerCase().includes(query);
    });
    const filtered = candidates.filter(r => selectedCategory === 'all' || A.category(r.category).id === selectedCategory);
    const categoryChips = [{id:'all',label:'All categories'}, ...A.categories].map(category => {
      const count=category.id==='all'?candidates.length:candidates.filter(r=>A.category(r.category).id===category.id).length;
      return `<button type="button" class="category-chip ${selectedCategory===category.id?'active':''}" data-action="filter-review-category" data-category="${e(category.id)}" aria-pressed="${selectedCategory===category.id}" aria-label="${e(category.label)}, ${count} reviews"><span>${e(category.label)}</span><span class="category-count" aria-hidden="true">${count}</span></button>`;
    }).join('');
    const noMatches = empty('No reviews match these filters', 'Category, search, and status work together. Try a broader selection.', selectedCategory!=='all'?b('Show all categories','clear-review-category','secondary'):b('Clear search and status','reset-review-filters','secondary'));
    return `${heading(A.state.role === 'coder' ? 'Find your next review' : 'Your reviews', 'Every review has a scope, an immutable commit, and a shared record.', A.state.role === 'coder' ? routeButton('Expert profile', 'verification') : routeButton('+ New review', 'new-review', 'primary'))}<div class="toolbar"><div class="search-wrap">${i('search')}<input aria-label="Search reviews" data-input="review-search" placeholder="Search title, repository, stack, or category" value="${e(A.context.reviewSearch || '')}"></div><span class="muted text-small" aria-live="polite">${filtered.length} ${filtered.length === 1 ? 'review' : 'reviews'}</span></div><div class="category-filter"><div class="category-filter-label">Task category <small>Counts reflect your search and status</small></div><div class="category-chips" role="group" aria-label="Filter reviews by task category">${categoryChips}</div></div><section class="panel"><div class="tabs">${[['all', 'All reviews'], ['active', 'In progress'], ['unassigned', 'Awaiting an expert'], ['completed', 'Completed']].map(([value, label]) => `<button class="${filter === value ? 'active' : ''}" data-action="filter-reviews" data-filter="${value}">${label}</button>`).join('')}</div>${filtered.length?reviewTable(filtered):reviews().length?noMatches:reviewTable([])}</section>${footer}`;
  }

  function expertCard(x) {
    return `<article class="panel expert-card">${A.avatar(x.initials, x.color)}<div class="expert-name"><h3>${e(x.name)}</h3>${x.verified ? t('Verified expert') : t('Verification pending', 'amber')}</div><small>${e(x.title)}</small><p class="bio">${e(x.bio)}</p><div class="skills">${(x.skills || []).map(s => t(s)).join('')}</div><div class="expert-footer"><div><strong>${money(x.rate)}</strong><small> / hour</small></div>${b('View profile', 'expert-profile', 'secondary', attr(x.id))}</div></article>`;
  }

  function expertList() {
    const query = (A.context.expertSearch || '').toLowerCase();
    const skill = A.context.expertSkill || 'all';
    const items = experts().filter(x => `${x.name} ${x.title} ${(x.skills || []).join(' ')}`.toLowerCase().includes(query) && (skill === 'all' || (x.skills || []).some(s => s.toLowerCase().includes(skill))));
    return `${heading('Expertise you can trust', 'Discover reviewers with the experience your code needs.', routeButton('Become an expert', 'verification', 'soft'))}<div class="toolbar"><div class="search-wrap">${i('search')}<input aria-label="Search experts" data-input="expert-search" value="${e(A.context.expertSearch || '')}" placeholder="Search name, skill, or specialty"></div><select aria-label="Expert specialty" data-input="expert-skill"><option value="all">All specialties</option>${[['security', 'Security'], ['typescript', 'TypeScript'], ['python', 'Python']].map(([v, l]) => `<option value="${v}" ${skill === v ? 'selected' : ''}>${l}</option>`).join('')}</select><span class="muted text-small">${items.length} sample profiles</span></div><div class="cards">${items.map(expertCard).join('')}</div>${!items.length ? empty('No matching experts', 'Try a different name or specialty.') : ''}${footer}`;
  }

  function repositories() {
    const unique = Array.from(new Map(reviews().map(r => [r.repo, r])).values());
    return `${heading('Your repositories', 'Access stays explicit. Know who can review each repository.', routeButton('+ Add repository', 'new-review', 'primary'))}<div class="notice">${i('lock')}<p>This preview records access confirmations locally. It does not connect to GitHub or grant repository permissions.</p></div><div class="cards">${unique.map(r => `<article class="panel repository-card"><div class="repo-card-heading"><span class="repo-icon">${i('git')}</span>${t('GitHub', 'blue')}</div><h2>${e(r.repo.replace(/^https?:\/\/github.com\//, ''))}</h2><p>${e(r.stack || 'Repository review')}</p>${categoryBadge(r)}<div class="kv"><span>AI review access</span>${r.access === 'demo_confirmed' ? t('Demo confirmed') : t('Needs access', 'amber')}</div><div class="kv"><span>Platform account</span><strong>antislop@bee3.in</strong></div><div class="kv"><span>Expert access</span>${r.expertId ? r.expertAccess === 'demo_confirmed' ? t('Demo confirmed') : t('Pending', 'amber') : '<span>Not assigned</span>'}</div><div class="card-actions">${b('Manage access', 'review-access', 'secondary', attr(r.id))}${b('View review', 'open-review', 'soft', attr(r.id))}</div></article>`).join('')}</div>${unique.length ? '' : empty('No repositories yet', 'Create a review to add your first repository.')}${footer}`;
  }

  function findings(r) {
    if (!(r.findings || []).length) return empty('No findings yet', 'Results will appear here once a real review service is connected.');
    return `<div class="notice">${i('file')}<p>These are sample findings for the UI preview, not results of an actual code scan.</p></div>${r.findings.map(f => `<article class="finding"><div class="finding-head">${t(f.severity || 'Medium', /critical|high/i.test(f.severity) ? 'red' : 'amber')}<h4>${e(f.title)}</h4></div><p>${e(f.description)}</p><code>${e(f.file || 'File reference unavailable')}</code><div class="finding-foot">${statusTag(f.status || 'Open')}${A.state.role === 'submitter' && f.status !== 'Verified' ? b(f.status === 'remediated' ? 'Reopen finding' : 'Mark remediated', 'finding-status', 'soft', `${attr(f.id)} data-review="${e(r.id)}"`) : ''}</div></article>`).join('')}`;
  }

  function proposals(r) {
    const items = r.proposals || [];
    return `<div class="notice">${i('users')}<p>Review scope and proposals before selecting an expert. Selection creates a demo assignment; no contract or payment is made.</p></div>${items.length ? items.map(p => {
      const x = experts().find(ex => ex.id === p.expertId);
      return `<article class="finding"><div class="repo-cell">${A.avatar(x?.initials || 'EX', x?.color)}<div><strong>${e(x?.name || 'Expert')}</strong><small>${e(x?.title || 'Code reviewer')}</small></div><strong class="push-right">${money(p.amount)}</strong></div><p style="margin-top:15px">${e(p.message)}</p><div class="card-actions">${x ? b('View profile', 'expert-profile', 'secondary', attr(x.id)) : ''}${x && A.state.role === 'submitter' ? b(r.expertId === x.id ? 'Selected' : 'Select expert', 'hire-expert', 'primary', `${attr(x.id)} data-review="${e(r.id)}" ${r.expertId === x.id ? 'disabled' : ''}`) : ''}</div></article>`;
    }).join('') : empty('A thoughtful match starts here', 'Invite an expert or browse the marketplace to find the right experience.', routeButton('Browse experts', 'experts', 'primary'))}`;
  }

  function detail() {
    const r = currentReview();
    if (!r) return `${heading('Review details', 'Create a review to get started.')}${empty('No review selected', 'Your repository and scope will appear here.', routeButton('New review', 'new-review', 'primary'))}`;
    const x = expertFor(r);
    const tab = A.context.detailTab || 'findings';
    const coder = A.state.role === 'coder';
    const verification=r.verification?`<h3>Verification plan</h3><div class="kv"><span>Job status</span><strong>${e(r.verification.status||'queued')}</strong></div>${(r.verification.plan?.runs||[]).map(run=>`<div class="kv"><span>${e(run.capability)}</span><span>${e(run.claim?.level||'planned')} · ${e(run.claim?.status||run.status)}</span></div>`).join('')}<p class="muted text-small">Evidence, findings, and attestation hashes appear after the worker completes the queued run.</p>`:'';
    const main = tab === 'scope' ? `<h3>Review brief</h3><p class="preserve-lines">${e(r.scope || 'No scope provided.')}</p><h3>Repository snapshot</h3><div class="kv"><span>Repository</span><span class="wrap-text">${e(r.repo)}</span></div><div class="kv"><span>Commit SHA</span><code class="wrap-text">${e(r.sha || 'Not specified')}</code></div><div class="kv"><span>Stack</span><span>${e(r.stack || 'Not specified')}</span></div>${verification}<div class="notice">${i('git')}<p>Review evidence belongs to this exact commit. A new commit needs a new assessment.</p></div>` : tab === 'proposals' ? proposals(r) : findings(r);
    return `${heading(r.title, `${r.stack || 'Code review'} · ${r.repo.replace(/^https?:\/\/github.com\//, '')}`, `${routeButton('All reviews', 'reviews')}${coder ? b('Submit proposal', 'apply-review', 'primary', attr(r.id)) : b('Manage access', 'review-access', 'primary', attr(r.id))}`)}<div class="review-meta">${statusTag(r.status)}${categoryBadge(r)}<span>${i('git')} Commit ${e((r.sha || 'Not set').slice(0, 8))}</span><span>${i('clock')} ${e(r.deadline || 'No deadline specified')}</span><span>${i('wallet')} ${money(r.budget)} budget</span></div><div class="detail-grid"><section class="panel"><div class="tabs">${[['findings', 'Findings'], ['scope', 'Scope & repository'], ['proposals', 'Expert proposals']].map(([v, l]) => `<button class="${tab === v ? 'active' : ''}" data-action="detail-tab" data-tab="${v}">${l}${v === 'findings' ? `<span>${(r.findings || []).length}</span>` : v === 'proposals' ? `<span>${(r.proposals || []).length}</span>` : ''}</button>`).join('')}</div><div class="detail-content">${main}</div></section><aside class="col-stack detail-side"><section class="panel"><div class="panel-head"><h2>Access checklist</h2>${i('lock')}</div><div class="side-content"><div class="access-step"><span class="number">1</span><div><h4>Platform review access</h4><p>Invite antislop@bee3.in through GitHub. The email alone does not grant access.</p>${r.access === 'demo_confirmed' ? t('Demo confirmation saved') : b('View access steps', 'review-access', 'secondary', attr(r.id))}</div></div><div class="access-step"><span class="number">2</span><div><h4>Select your expert</h4><p>${x ? e(x.name) + ' is assigned in this demo.' : 'Choose a reviewer after comparing experience and scope.'}</p>${x ? t('Demo assignment') : routeButton('Find an expert', 'experts', 'secondary')}</div></div><div class="access-step"><span class="number">3</span><div><h4>Share expert access</h4><p>${x ? 'Grant scoped access to your selected reviewer on GitHub.' : 'This step opens after you select an expert.'}</p>${x ? r.expertAccess === 'demo_confirmed' ? t('Demo confirmation saved') : b('Expert access steps', 'expert-access', 'secondary', attr(r.id)) : t('Waiting for assignment', 'amber')}</div></div></div></section>${x ? `<section class="panel"><div class="panel-head"><h2>Your reviewer</h2></div><div class="side-content"><div class="repo-cell">${A.avatar(x.initials, x.color)}<div><strong>${e(x.name)}</strong><small>${e(x.title)}</small></div></div><div class="card-actions">${b('View profile', 'expert-profile', 'secondary', attr(x.id))}${routeButton('Message', 'messages', 'soft')}</div></div></section>` : ''}<section class="panel"><div class="panel-head"><h2>Resolution workflow</h2>${i('check')}</div><div class="side-content"><p class="muted text-small">Submitters can mark sample findings as remediated. Independent retesting is required before a real finding is verified.</p></div></section></aside></div>${footer}`;
  }

  function messages() {
    const r = currentReview();
    if (!r) return `${heading('Messages', 'Keep review decisions together.')}${empty('No conversations yet', 'Create a review to start a conversation.')}`;
    const x = expertFor(r);
    return `${heading('Messages', 'One shared conversation for scope, findings, and follow-up.')}<section class="panel messages-grid"><aside class="thread-list">${reviews().map(item => `<button class="thread ${item.id === r.id ? 'active' : ''}" data-action="message-thread" ${attr(item.id)}>${A.avatar(expertFor(item)?.initials || 'AS', expertFor(item)?.color)}<span><strong>${e(item.title)}</strong><small>${e(expertFor(item)?.name || 'Antislop workspace')}</small></span></button>`).join('')}</aside><div class="chat"><div class="chat-head"><div><h3>${e(r.title)}</h3><p>${e(x?.name || 'Your review workspace')}</p></div>${t('Local demo', 'amber')}</div><div class="chat-messages" aria-live="polite">${(r.messages || []).map(m => `<div class="bubble ${m.from === 'You' || m.from === A.state.user?.name ? 'mine' : ''}"><strong>${e(m.from)}</strong><p>${e(m.text)}</p><small>${e(m.time || 'Just now')}</small></div>`).join('') || '<div class="empty"><p>Clarify the scope or leave a note for your reviewer.</p></div>'}</div><form class="chat-compose" data-form="send-message"><input type="hidden" name="reviewId" value="${e(r.id)}"><input required name="message" maxlength="2000" aria-label="Message" placeholder="Write a message…">${b(`${i('send')} Send`, '', 'primary', 'type="submit"')}</form><p class="message-demo-note">Messages are stored in this browser only. No email or external notification is sent.</p></div></section>${footer}`;
  }

  function billing() {
    return `${heading('Billing & budgets', 'Keep your review spend easy to understand.')}<div class="stats">${stat('Review budgets', money(reviews().reduce((n, r) => n + Number(r.budget || 0), 0)), 'Proposed scope budgets', 'wallet')}${stat('Charged to date', '$0', 'No payments connected', 'check')}${stat('Pending invoices', '0', 'No live invoices', 'file')}${stat('Current plan', 'Preview', 'Explore the full workflow', 'star')}</div><div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2>Budget overview</h2><p>Amounts below are planning figures, not transactions</p></div>${t('Mock billing', 'amber')}</div><div class="table-scroll"><table><thead><tr><th>REVIEW</th><th>BUDGET</th><th>PAYMENT STATUS</th></tr></thead><tbody>${reviews().map(r => `<tr><td>${e(r.title)}</td><td>${money(r.budget)}</td><td>${t('Not charged', 'blue')}</td></tr>`).join('')}</tbody></table></div></section><section class="panel"><div class="panel-head"><h2>Payment method</h2>${i('wallet')}</div><div class="side-content"><p class="muted">Payment processing and escrow are not configured in this UI preview.</p><div class="notice">${i('lock')}<p>No payment details are collected.</p></div>${b('How billing will work', 'billing-info', 'secondary')}</div></section></div>${footer}`;
  }

  function settings() {
    return `${heading('Workspace settings', 'Your profile, your preferences, your working style.')}<section class="panel form-panel"><div class="section-title"><h2>Profile details</h2><p>Updates are saved to this browser for the preview.</p></div><form data-form="save-settings"><div class="form-grid"><div class="field"><label for="settings-name">Full name</label><input id="settings-name" name="name" required maxlength="80" value="${e(A.state.user?.name || '')}"></div><div class="field"><label for="settings-email">Email address</label><input id="settings-email" name="email" type="email" required value="${e(A.state.user?.email || '')}"><small>Editing this demo profile does not verify ownership of the address.</small></div><div class="field full"><label for="settings-workspace">Workspace name</label><input id="settings-workspace" name="workspace" maxlength="80" value="${e(A.state.workspace || 'Personal workspace')}"></div></div><div class="form-actions"><small>Local preview preferences</small>${b('Save changes', '', 'primary', 'type="submit"')}</div></form><hr><div class="section-title"><h2>Review access account</h2><p>Submitters use antislop@bee3.in when following repository access instructions.</p></div><div class="notice">${i('lock')}<p>GitHub installation, Google sign-in, email OTP delivery, and team permissions need connected backend services before production use.</p></div></section>${footer}`;
  }

  Object.assign(A.views, { overview, reviews: reviewList, experts: expertList, repositories, review: detail, messages, billing, settings });
  Object.assign(A.actions, {
    'dashboard-go': (el) => A.go(el.dataset.route),
    'open-review': (el) => { A.state.activeReview = el.dataset.id; A.context.detailTab = 'findings'; A.persist(); A.go('review'); },
    'filter-reviews': (el) => { A.context.reviewFilter = el.dataset.filter; A.render(); },
    'filter-review-category': (el) => { const id=el.dataset.category;if(id!=='all'&&!A.categories.some(category=>category.id===id))return;A.context.reviewCategory=id;A.render();document.querySelector(`[data-action="filter-review-category"][data-category="${id}"]`)?.focus(); },
    'clear-review-category': () => { A.context.reviewCategory='all';A.render();document.querySelector('[data-action="filter-review-category"][data-category="all"]')?.focus(); },
    'reset-review-filters': () => { A.context.reviewCategory='all';A.context.reviewFilter='all';A.context.reviewSearch='';A.render();document.querySelector('[data-input="review-search"]')?.focus(); },
    'detail-tab': (el) => { A.context.detailTab = el.dataset.tab; A.render(); },
    'message-thread': (el) => { A.state.activeReview = el.dataset.id; A.persist(); A.render(); },
    'expert-profile': (el) => {
      const x = experts().find(ex => ex.id === el.dataset.id);
      if (!x) return;
      A.modal(x.name, x.title, `<div class="expert-modal-profile">${A.avatar(x.initials, x.color)}${x.verified ? t('Verified · demo profile') : t('Pending verification', 'amber')}</div><p class="muted">${e(x.bio)}</p><div class="skills profile-skills">${(x.skills || []).map(s => t(s)).join('')}</div><div class="kv"><span>Hourly rate</span><strong>${money(x.rate)} / hour</strong></div><div class="kv"><span>GitHub</span><span>${e(x.github || 'Not provided')}</span></div><div class="notice">${i('shield')}<p>Demo profile for design review. Production verification is performed by a separate review team.</p></div>${A.state.role === 'submitter' ? b('Select for a review', 'hire-expert', 'primary', attr(x.id)) : routeButton('Review opportunities', 'reviews', 'primary')}`);
    },
    'hire-expert': (el) => {
      const x = experts().find(ex => ex.id === el.dataset.id);
      if (!x) return;
      if (A.state.role !== 'submitter') return A.toast('Switch to the submitter workspace to select an expert.');
      if (!x.verified) return A.toast('This profile is awaiting verification.');
      const choices = reviews();
      if (!choices.length) { A.closeModal(); A.go('new-review'); return; }
      const selected = el.dataset.review || A.state.activeReview || choices[0].id;
      A.modal('Select your reviewer', `Bring ${x.name} into the review workspace.`, `<form data-form="confirm-hire"><input type="hidden" name="expertId" value="${e(x.id)}"><div class="field"><label for="hire-review">Choose a review</label><select id="hire-review" name="reviewId">${choices.map(r => `<option value="${e(r.id)}" ${r.id === selected ? 'selected' : ''}>${e(r.title)}</option>`).join('')}</select></div><div class="notice">${i('lock')}<p>This is a demo assignment. You will next see the GitHub access checklist. No access, payment, or external invitation is sent.</p></div>${b('Confirm demo assignment', '', 'primary', 'type="submit"')}</form>`);
    },
    'apply-review': (el) => {
      if (A.state.role !== 'coder') return A.toast('Use the coder workspace to submit a proposal.');
      if (!approved()) { A.toast('Your expert profile needs team approval before you can apply.'); A.go('verification'); return; }
      const r = reviews().find(item => item.id === el.dataset.id);
      if (!r) return;
      A.modal('A thoughtful proposal', r.title, `<form data-form="submit-proposal"><input type="hidden" name="reviewId" value="${e(r.id)}"><div class="field"><label for="proposal-message">How would you approach this review?</label><textarea id="proposal-message" name="message" required minlength="20" maxlength="2000" placeholder="Relevant experience, approach, and what you will deliver…"></textarea></div><div class="field"><label for="proposal-amount">Proposed fixed fee (USD)</label><input id="proposal-amount" name="amount" type="number" min="1" max="100000" required value="${Number(r.budget || 500)}"></div><p class="muted text-small">Stored locally. This does not create a contract or notify a submitter.</p><div class="card-actions">${b('Save demo proposal', '', 'primary', 'type="submit"')}</div></form>`);
    },
    'finding-status': (el) => {
      const r = reviews().find(item => item.id === el.dataset.review);
      const f = r?.findings.find(item => item.id === el.dataset.id);
      if (!f || A.state.role !== 'submitter') return;
      f.status = f.status === 'remediated' ? 'open' : 'remediated';
      A.persist(); A.render(); A.toast(f.status === 'remediated' ? 'Demo finding marked remediated. Independent verification is still required.' : 'Demo finding reopened.');
    },
    'billing-info': () => A.modal('Clear budgets. Clear commitments.', 'Billing workflow preview', '<p class="muted">A production review would display its scope, agreed price, payment terms, and acceptance criteria before a payment. Charges, invoices, payouts, and disputes require a payment integration.</p><div class="notice">No payment is requested in this preview.</div>')
  });
  Object.assign(A.forms, {
    'send-message': (form) => {
      const data = new FormData(form);
      const r = reviews().find(item => item.id === data.get('reviewId'));
      const text = String(data.get('message') || '').trim();
      if (!r || !text) return;
      (r.messages ||= []).push({ id: 'm' + Date.now(), from: 'You', text: text.slice(0, 2000), time: 'Just now · local demo' });
      A.persist(); A.render(); A.toast('Message saved locally.');
    },
    'save-settings': (form) => {
      const data = new FormData(form);
      A.state.user = { ...A.state.user, name: String(data.get('name') || '').trim(), email: String(data.get('email') || '').trim() };
      A.state.workspace = String(data.get('workspace') || '').trim();
      A.persist(); A.render(); A.toast('Preview profile saved.');
    },
    'confirm-hire': (form) => {
      if (A.state.role !== 'submitter') return;
      const data = new FormData(form);
      const r = reviews().find(item => item.id === data.get('reviewId'));
      const x = experts().find(item => item.id === data.get('expertId'));
      if (!r || !x?.verified) return;
      r.expertId = x.id; r.expertAccess = 'pending';
      A.state.activeReview = r.id;
      (A.state.events ||= []).unshift({ text: `${x.name} selected for ${r.title} in this demo.`, time: 'Just now', icon: 'users' });
      A.persist(); A.closeModal(); A.go('review'); A.toast('Demo reviewer selected. Next: grant scoped GitHub access.');
    },
    'submit-proposal': (form) => {
      if (A.state.role !== 'coder' || !approved()) return;
      const data = new FormData(form);
      const r = reviews().find(item => item.id === data.get('reviewId'));
      const message = String(data.get('message') || '').trim();
      const amount = Number(data.get('amount'));
      if (!r || message.length < 20 || !Number.isFinite(amount) || amount < 1 || amount > 100000) return A.toast('Add a proposal of at least 20 characters and a valid fee.');
      const application = A.state.application;
      let x = experts().find(ex => ex.email === application.email);
      if (!x) {
        x = { id: 'e' + Date.now(), name: application.name, email: application.email, initials: application.name.split(/\s+/).filter(Boolean).slice(0, 2).map(s => s[0]).join('').toUpperCase(), title: application.specialty || 'Verified code reviewer', skills: [application.specialty || 'Code review'], bio: application.bio || 'Approved expert profile in this UI preview.', rate: 0, verified: true, github: application.github, color: 'blue' };
        A.state.experts.push(x);
      }
      const proposal = { id: 'p' + Date.now(), expertId: x.id, message: message.slice(0, 2000), amount };
      (r.proposals ||= []).push(proposal);
      A.state.activeReview = r.id; A.context.detailTab = 'proposals';
      A.persist(); A.closeModal(); A.go('review'); A.toast('Demo proposal saved locally.');
    }
  });
  A.inputs ||= {};
  function updateSearch(key, name, value, element) {
    const start = element?.selectionStart;
    const end = element?.selectionEnd;
    A.context[key] = value; A.render();
    const input = document.querySelector(`[data-input="${name}"]`);
    input?.focus();
    if (input && typeof start === 'number') input.setSelectionRange(start, end);
  }
  Object.assign(A.inputs, {
    'review-search': (value, element) => updateSearch('reviewSearch', 'review-search', value, element),
    'expert-search': (value, element) => updateSearch('expertSearch', 'expert-search', value, element),
    'expert-skill': (value) => { A.context.expertSkill = value; A.render(); }
  });
})();
