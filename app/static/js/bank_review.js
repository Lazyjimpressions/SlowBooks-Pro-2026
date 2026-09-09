/**
 * Imported-transaction review. This layer edits and approves versioned
 * proposals only; Phase 4 owns proposal-driven ledger posting.
 */
(function () {
    const intentLabels = {
        direct_expense: 'Direct expense', direct_income: 'Direct income',
        customer_payment: Terms.text('Customer payment candidate'), bill_payment: 'Bill payment candidate',
        transfer: 'Transfer', owner_contribution: 'Owner contribution', owner_draw: 'Owner draw',
        loan_proceeds: 'Loan proceeds', loan_payment: 'Loan payment',
        investment_activity: 'Investment activity', reimbursement: 'Reimbursement', unknown: 'Unknown',
    };
    const routeLabels = {
        direct: 'Direct', transfer: 'Transfer', customer_payment: Terms.text('Customer payment'),
        bill_payment: 'Bill payment', hold: 'Hold for domain workflow',
    };

    const options = (values, selected, labels = {}) => Object.keys(values).map(value =>
        `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(labels[value] || values[value])}</option>`
    ).join('');

    BankingPage.renderReviewQueue = async function (bankAccountId = null, status = 'proposed') {
        BankingPage._reviewFilter = { bankAccountId, status };
        const query = new URLSearchParams({ status });
        if (bankAccountId) query.set('bank_account_id', bankAccountId);
        let items, classes;
        try {
            [items, classes] = await Promise.all([
                API.get(`/banking/review?${query.toString()}`),
                API.get('/classes'),
            ]);
        }
        catch (err) { toast(err.message, 'error'); return; }
        const classNames = new Map(classes.map(item => [item.id, item.name]));

        const statusButtons = ['unresolved', 'proposed', 'approved', 'posted'].map(value =>
            `<button class="btn btn-sm ${status === value ? 'btn-primary' : 'btn-secondary'}"
                data-bank-review-status="${value}" data-bank-account-id="${bankAccountId || ''}">${value[0].toUpperCase() + value.slice(1)}</button>`
        ).join('');
        const rows = items.map(item => {
            const t = item.transaction;
            const p = item.active_proposal;
            const evidence = [t.payee, t.description].filter(Boolean).map(escapeHtml).join('<br>');
            const summary = p
                ? `<strong>${escapeHtml(intentLabels[p.intent] || p.intent)}</strong><br>
                   ${escapeHtml(p.normalized_counterparty || 'No counterparty')} · ${escapeHtml(p.class_resolution === 'assigned' ? (classNames.get(p.class_id) || `Class #${p.class_id}`) : p.class_resolution.replaceAll('_', ' '))}<br>
                   <span style="font-size:10px;color:var(--text-muted);">${escapeHtml(p.proposal_source)}${p.confidence !== null ? ` · ${Math.round(Number(p.confidence) * 100)}%` : ''}</span>`
                : '<span class="badge badge-pending">Needs suggestion</span>';
            const action = p
                ? `<a class="btn btn-sm btn-primary" href="#/bank-review/${t.id}">Review</a>`
                : `<button class="btn btn-sm btn-secondary" data-bank-suggest-id="${t.id}">Suggest</button>`;
            const bulk = p && p.status === 'proposed' && ['direct_expense', 'direct_income'].includes(p.intent)
                ? `<input type="checkbox" class="bank-review-bulk" value="${p.id}" aria-label="Select proposal ${p.id}">`
                : '';
            return `<tr>
                <td>${bulk}</td><td>${formatDate(t.date)}</td><td>${evidence}</td>
                <td class="amount" style="color:${Number(t.amount) >= 0 ? 'var(--success)' : 'var(--danger)'}">${formatCurrency(t.amount)}</td>
                <td>${summary}</td><td class="actions">${action}</td></tr>`;
        }).join('');
        $('#page-content').innerHTML = `
            <div class="page-header"><h2>Banking Review</h2>
                ${bankAccountId ? `<button class="btn btn-secondary" data-bank-register-id="${bankAccountId}">Back</button>` : '<a class="btn btn-secondary" href="#/banking">Back</a>'}</div>
            <div class="toolbar" style="display:flex;gap:6px;flex-wrap:wrap;">${statusButtons}
                ${status === 'proposed' ? '<button class="btn btn-sm btn-secondary" data-bank-review-bulk>Approve Selected Identical</button>' : ''}
            </div>
            <p style="font-size:11px;color:var(--text-muted);margin:8px 0;">Imported evidence is never edited here. Approval records a reviewed classification and does not post a journal entry.</p>
            <div class="table-container"><table><thead><tr><th scope="col"></th><th scope="col">Date</th><th scope="col">Imported evidence</th><th scope="col" class="amount">Amount</th><th scope="col">Proposal</th><th scope="col">Action</th></tr></thead>
                <tbody>${rows || '<tr><td colspan="6" style="text-align:center;">No transactions in this review state</td></tr>'}</tbody></table></div>`;
    };

    BankingPage.suggestReview = async function (transactionId) {
        try {
            await API.post(`/banking/transactions/${transactionId}/suggest`, {});
            await BankingPage.showReview(transactionId);
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.showReview = async function (transactionId, selectedContact = null) {
        let detail, accounts, classes, customers, vendors;
        try {
            [detail, accounts, classes, customers, vendors] = await Promise.all([
                API.get(`/banking/transactions/${transactionId}/review`), API.get('/accounts'),
                API.get('/classes'), API.get('/customers?active_only=true'), API.get('/vendors?active_only=true'),
            ]);
        } catch (err) { toast(err.message, 'error'); return; }
        const p = detail.active_proposal;
        if (!p) { await BankingPage.suggestReview(transactionId); return; }
        BankingPage._activeReview = { detail, accounts, classes, customers, vendors };
        if (selectedContact) {
            p.counterparty_resolution = selectedContact.type;
            p.counterparty_role = selectedContact.type === 'customer' ? 'payer' : 'payee';
            p.customer_id = selectedContact.type === 'customer' ? selectedContact.id : null;
            p.vendor_id = selectedContact.type === 'vendor' ? selectedContact.id : null;
        }
        const t = detail.transaction;
        const acctOpts = accounts.filter(a => a.is_active).map(a =>
            `<option value="${a.id}" ${a.id === p.counter_account_id ? 'selected' : ''}>${escapeHtml(a.account_number || '')} - ${escapeHtml(a.name)} (${escapeHtml(a.account_type)})</option>`).join('');
        const classOpts = classes.filter(c => !c.is_archived && !c.is_system_default).map(c =>
            `<option value="${c.id}" ${c.id === p.class_id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('');
        const customerOpts = customers.map(c => `<option value="${c.id}" ${c.id === p.customer_id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('');
        const vendorOpts = vendors.map(v => `<option value="${v.id}" ${v.id === p.vendor_id ? 'selected' : ''}>${escapeHtml(v.name)}</option>`).join('');
        const history = detail.proposal_history.map(h =>
            `<li>Revision ${h.revision}: ${escapeHtml(h.status)} · ${escapeHtml(h.proposal_source)} · ${escapeHtml(h.created_by)}${h.reviewed_by ? `; reviewed by ${escapeHtml(h.reviewed_by)}` : ''}</li>`).join('');
        const components = (p.confidence_components || []).map(c =>
            `<li><strong>${escapeHtml(c.name.replaceAll('_', ' '))}</strong>: ${escapeHtml(c.detail)}</li>`).join('');

        const actions = p.status === 'posted'
            ? `<button type="button" class="btn btn-danger" data-bank-review-reverse="${p.id}">Reverse &amp; Reopen</button>`
            : p.status === 'approved'
                ? `<button type="button" class="btn btn-secondary" data-bank-review-supersede="${p.id}">Supersede</button>
                   <button type="submit" class="btn btn-secondary">Save Correction</button>
                   <button type="button" class="btn btn-primary" data-bank-review-post="${p.id}">Post Approved Proposal</button>`
                : `<button type="button" class="btn btn-secondary" data-bank-review-reject="${p.id}">Reject</button>
                   <button type="button" class="btn btn-secondary" data-bank-review-supersede="${p.id}">Supersede</button>
                   <button type="submit" class="btn btn-secondary">Save Correction</button>
                   <button type="button" class="btn btn-primary" data-bank-review-approve="${p.id}">Save &amp; Approve</button>`;
        openModal('Review Imported Transaction', `
            <div style="padding:10px;border:1px solid var(--border);margin-bottom:12px;background:var(--surface-alt,transparent);">
                <strong>Imported evidence — read only</strong><br>${formatDate(t.date)} · ${formatCurrency(t.amount)}<br>
                <strong>Payee:</strong> ${escapeHtml(t.payee || '—')}<br><strong>Description:</strong> ${escapeHtml(t.description || '—')}<br>
                <strong>Check/reference:</strong> ${escapeHtml(t.check_number || '—')}
            </div>
            <form id="bank-review-form" data-proposal-id="${p.id}">
                <div class="form-grid">
                    <div class="form-group"><label>Intent *</label><select name="intent" data-bank-review-intent>${options(intentLabels, p.intent)}</select></div>
                    <div class="form-group"><label>Posting route *</label><select name="posting_route">${options(routeLabels, p.posting_route)}</select></div>
                    <div class="form-group full-width"><label>Clean counterparty name</label><input name="normalized_counterparty" maxlength="200" value="${escapeHtml(p.normalized_counterparty || '')}"></div>
                    <div class="form-group"><label>Counterparty decision *</label>
                        <select name="counterparty_resolution" data-bank-review-contact>
                            ${options({unresolved:'Unresolved',text_only:'Reviewed text only',customer:'Existing customer',vendor:'Existing vendor',not_applicable:'Not applicable'}, p.counterparty_resolution)}
                        </select></div>
                    <div class="form-group"><label>Role *</label><select name="counterparty_role">
                        <option value="">—</option>${options({payer:'Payer',payee:'Payee',not_applicable:'Not applicable'}, p.counterparty_role || '')}</select></div>
                    <div class="form-group bank-review-customer"><label>Existing customer</label><select name="customer_id"><option value="">— choose —</option>${customerOpts}</select>
                        <button type="button" class="btn btn-sm btn-secondary" data-bank-contact-gate="customer" data-bank-transaction-id="${transactionId}">Create customer…</button></div>
                    <div class="form-group bank-review-vendor"><label>Existing vendor</label><select name="vendor_id"><option value="">— choose —</option>${vendorOpts}</select>
                        <button type="button" class="btn btn-sm btn-secondary" data-bank-contact-gate="vendor" data-bank-transaction-id="${transactionId}">Create vendor…</button></div>
                    <div class="form-group"><label>Counter-account</label><select name="counter_account_id"><option value="">— unresolved / domain workflow —</option>${acctOpts}</select></div>
                    <div class="form-group"><label>${T('Class')} decision *</label><select name="class_resolution" data-bank-review-class-resolution>
                        ${options({unresolved:'Unresolved',assigned:'Assigned class',personal_no_class:'Personal / no class (legacy policy)',not_applicable:'Not applicable (balance sheet)'}, p.class_resolution)}
                        </select></div>
                    <div class="form-group bank-review-class"><label>${T('Class')}</label><select name="class_id"><option value="">— choose —</option>${classOpts}</select></div>
                    <div class="form-group"><label>Paired bank row</label><input name="paired_bank_transaction_id" type="number" value="${p.paired_bank_transaction_id || ''}"></div>
                    <div class="form-group full-width"><label>Review rationale</label><textarea name="rationale" rows="2">${escapeHtml(p.rationale || '')}</textarea></div>
                </div>
                <div style="font-size:11px;margin-top:10px;"><strong>Suggestion source:</strong> ${escapeHtml(p.proposal_source)} · confidence ${p.confidence === null ? 'not scored' : Math.round(Number(p.confidence) * 100) + '%'}
                    <br>${escapeHtml(p.rationale || '')}<ul>${components}</ul></div>
                <details style="margin-top:8px;"><summary>Proposal history</summary><ul>${history}</ul></details>
                <div class="form-actions">${actions}</div>
            </form>`);
        BankingPage.syncReviewContact(p.counterparty_resolution);
        BankingPage.syncReviewClass(p.class_resolution);
    };

    BankingPage.syncReviewIntent = function (intent) {
        const form = document.getElementById('bank-review-form');
        if (!form) return;
        const route = {direct_expense:'direct',direct_income:'direct',customer_payment:'customer_payment',bill_payment:'bill_payment',transfer:'transfer',owner_contribution:'direct',owner_draw:'direct',loan_proceeds:'direct',loan_payment:'hold',investment_activity:'hold',reimbursement:'hold',unknown:'hold'}[intent];
        form.posting_route.value = route;
        if (intent === 'transfer') {
            form.counterparty_resolution.value = 'not_applicable'; form.counterparty_role.value = 'not_applicable';
            form.class_resolution.value = 'not_applicable';
            BankingPage.syncReviewContact('not_applicable'); BankingPage.syncReviewClass('not_applicable');
        }
    };
    BankingPage.syncReviewContact = function (resolution) {
        document.querySelectorAll('.bank-review-customer').forEach(el => el.style.display = resolution === 'customer' ? '' : 'none');
        document.querySelectorAll('.bank-review-vendor').forEach(el => el.style.display = resolution === 'vendor' ? '' : 'none');
    };
    BankingPage.syncReviewClass = function (resolution) {
        document.querySelectorAll('.bank-review-class').forEach(el => el.style.display = resolution === 'assigned' ? '' : 'none');
    };

    BankingPage.reviewPayload = function () {
        const form = document.getElementById('bank-review-form');
        const contact = form.counterparty_resolution.value;
        const classResolution = form.class_resolution.value;
        return {
            intent: form.intent.value, posting_route: form.posting_route.value,
            normalized_counterparty: form.normalized_counterparty.value.trim() || null,
            counterparty_role: form.counterparty_role.value || null,
            counterparty_resolution: contact,
            customer_id: contact === 'customer' && form.customer_id.value ? Number(form.customer_id.value) : null,
            vendor_id: contact === 'vendor' && form.vendor_id.value ? Number(form.vendor_id.value) : null,
            counter_account_id: form.counter_account_id.value ? Number(form.counter_account_id.value) : null,
            class_resolution: classResolution,
            class_id: classResolution === 'assigned' && form.class_id.value ? Number(form.class_id.value) : null,
            paired_bank_transaction_id: form.paired_bank_transaction_id.value ? Number(form.paired_bank_transaction_id.value) : null,
            proposal_source: 'human', rationale: form.rationale.value.trim() || null,
        };
    };

    BankingPage.saveReview = async function (event, proposalId, approve) {
        event.preventDefault();
        try {
            const replacement = await API.put(`/banking/proposals/${proposalId}`, BankingPage.reviewPayload());
            if (approve) await API.post(`/banking/proposals/${replacement.id}/approve`, {});
            toast(approve ? 'Proposal approved; no ledger entry posted yet' : 'Correction saved');
            closeModal();
            const f = BankingPage._reviewFilter || {};
            BankingPage.renderReviewQueue(f.bankAccountId || null, approve ? 'approved' : 'proposed');
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.rejectReview = async function (proposalId) {
        const note = prompt('Why is this proposal being rejected?') || '';
        try {
            await API.post(`/banking/proposals/${proposalId}/reject`, { note });
            closeModal(); toast('Proposal rejected');
            const f = BankingPage._reviewFilter || {};
            BankingPage.renderReviewQueue(f.bankAccountId || null, 'proposed');
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.supersedeReview = async function (proposalId) {
        const note = prompt('Why is this proposal being superseded?') || '';
        try {
            await API.post(`/banking/proposals/${proposalId}/supersede`, { note });
            closeModal(); toast('Proposal superseded; the bank row is unresolved again');
            const f = BankingPage._reviewFilter || {};
            BankingPage.renderReviewQueue(f.bankAccountId || null, 'unresolved');
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.bulkApproveSelected = async function () {
        const proposal_ids = Array.from(document.querySelectorAll('.bank-review-bulk:checked')).map(el => Number(el.value));
        if (proposal_ids.length < 2) { toast('Select at least two identical proposals', 'error'); return; }
        if (!confirm(`Approve ${proposal_ids.length} identical proposals? This does not post them.`)) return;
        try {
            await API.post('/banking/proposals/bulk-approve', { proposal_ids });
            toast(`${proposal_ids.length} proposals approved`);
            const f = BankingPage._reviewFilter || {};
            BankingPage.renderReviewQueue(f.bankAccountId || null, 'proposed');
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.postApprovedReview = async function (proposalId) {
        if (!confirm('Post this approved proposal to the ledger?')) return;
        try {
            const result = await API.post(`/banking/proposals/${proposalId}/post`, {});
            toast(`Posted journal transaction ${result.transaction_id}`);
            closeModal();
            const f = BankingPage._reviewFilter || {};
            BankingPage.renderReviewQueue(f.bankAccountId || null, 'approved');
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.reversePostedReview = async function (proposalId) {
        const reversalDate = prompt('Reversal date (YYYY-MM-DD)', todayISO());
        if (!reversalDate) return;
        const note = prompt('Reason for reversal and correction') || '';
        if (!confirm('Post a reversing journal entry and reopen this row for review?')) return;
        try {
            const result = await API.post(`/banking/proposals/${proposalId}/reverse`, {
                reversal_date: reversalDate, note,
            });
            toast(`Reversed and reopened ${result.replacement_proposal_ids.length} proposal(s)`);
            closeModal();
            const f = BankingPage._reviewFilter || {};
            BankingPage.renderReviewQueue(f.bankAccountId || null, 'proposed');
        } catch (err) { toast(err.message, 'error'); }
    };

    BankingPage.showContactGate = function (type, transactionId) {
        const form = document.getElementById('bank-review-form');
        const proposedName = form ? form.normalized_counterparty.value.trim() : '';
        const contactLabel = type === 'customer' ? T('Customer') : 'Vendor';
        const moduleLabel = type === 'customer' ? T('Customers') : 'Vendors';
        openModal(`Create ${contactLabel} Record`, `
            <p style="font-size:12px;">This creates a real record in the ${moduleLabel} module. It is not merely a bank-feed label.</p>
            <form data-bank-create-contact="${type}" data-bank-transaction-id="${transactionId}">
                <div class="form-group"><label>Name *</label><input name="name" maxlength="200" required value="${escapeHtml(proposedName)}"></div>
                <div class="form-actions"><button type="button" class="btn btn-secondary" data-bank-review-id="${transactionId}">Cancel</button>
                    <button type="submit" class="btn btn-primary">Check &amp; Create</button></div>
            </form>`);
    };

    BankingPage.createContactFromReview = async function (event, type, transactionId) {
        event.preventDefault();
        const name = event.target.name.value.trim();
        try {
            const path = type === 'customer' ? '/customers' : '/vendors';
            const check = await API.get(`${path}/check-duplicate?name=${encodeURIComponent(name)}`);
            if (check.duplicates.length) {
                const names = check.duplicates.map(d => d.name).join(', ');
                toast(`Possible duplicate: ${names}. Return to review and select the existing record.`, 'error');
                return;
            }
            const moduleLabel = type === 'customer' ? T('Customers') : 'Vendors';
            const contactLabel = type === 'customer' ? T('Customer') : 'Vendor';
            if (!confirm(`Create ${name} in the ${moduleLabel} module?`)) return;
            const contact = await API.post(path, { name });
            toast(`${contactLabel} created`);
            await BankingPage.showReview(transactionId, { type, id: contact.id });
        } catch (err) { toast(err.message, 'error'); }
    };

    // New review controls use delegated listeners so they work under both the
    // browser CSP and the desktop web view without adding more inline-handler
    // debt to the application.
    document.addEventListener('click', event => {
        const target = event.target.closest('[data-bank-review-id], [data-bank-suggest-id], [data-bank-review-status], [data-bank-register-id], [data-bank-review-bulk], [data-bank-review-reject], [data-bank-review-supersede], [data-bank-review-approve], [data-bank-review-post], [data-bank-review-reverse], [data-bank-contact-gate]');
        if (!target) return;
        if (target.dataset.bankReviewId) BankingPage.showReview(Number(target.dataset.bankReviewId));
        else if (target.dataset.bankSuggestId) BankingPage.suggestReview(Number(target.dataset.bankSuggestId));
        else if (target.dataset.bankReviewStatus) BankingPage.renderReviewQueue(Number(target.dataset.bankAccountId) || null, target.dataset.bankReviewStatus);
        else if (target.dataset.bankRegisterId) BankingPage.viewRegister(Number(target.dataset.bankRegisterId));
        else if (target.hasAttribute('data-bank-review-bulk')) BankingPage.bulkApproveSelected();
        else if (target.dataset.bankReviewReject) BankingPage.rejectReview(Number(target.dataset.bankReviewReject));
        else if (target.dataset.bankReviewSupersede) BankingPage.supersedeReview(Number(target.dataset.bankReviewSupersede));
        else if (target.dataset.bankReviewApprove) BankingPage.saveReview(event, Number(target.dataset.bankReviewApprove), true);
        else if (target.dataset.bankReviewPost) BankingPage.postApprovedReview(Number(target.dataset.bankReviewPost));
        else if (target.dataset.bankReviewReverse) BankingPage.reversePostedReview(Number(target.dataset.bankReviewReverse));
        else if (target.dataset.bankContactGate) BankingPage.showContactGate(target.dataset.bankContactGate, Number(target.dataset.bankTransactionId));
    });
    document.addEventListener('change', event => {
        if (event.target.matches('[data-bank-review-intent]')) BankingPage.syncReviewIntent(event.target.value);
        if (event.target.matches('[data-bank-review-contact]')) BankingPage.syncReviewContact(event.target.value);
        if (event.target.matches('[data-bank-review-class-resolution]')) BankingPage.syncReviewClass(event.target.value);
    });
    document.addEventListener('submit', event => {
        if (event.target.matches('#bank-review-form')) {
            BankingPage.saveReview(event, Number(event.target.dataset.proposalId), false);
        } else if (event.target.matches('[data-bank-create-contact]')) {
            BankingPage.createContactFromReview(event, event.target.dataset.bankCreateContact, Number(event.target.dataset.bankTransactionId));
        }
    });
})();
