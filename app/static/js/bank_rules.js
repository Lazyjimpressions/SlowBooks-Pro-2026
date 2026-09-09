/**
 * Bank Rules — auto-categorize imported bank transactions by payee pattern
 * Phase 10: Quick Wins + Medium Effort Features
 */
const BankRulesPage = {
    async render() {
        const rules = await API.get('/bank-rules');
        let html = `
            <div class="page-header">
                <h2>Bank Rules</h2>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="BankRulesPage.showForm()">+ New Rule</button>
                    <button class="btn btn-secondary" onclick="BankRulesPage.applyAll()">Apply Rules Now</button>
                </div>
            </div>
            <p style="font-size:11px; color:var(--text-muted); margin-bottom:12px;">
                Rules propose reviewed accounting mappings; they never approve or post. Higher priority rules are checked first.
            </p>`;

        if (rules.length === 0) {
            html += '<div class="empty-state"><p>No bank rules yet. Create one to auto-categorize transactions.</p></div>';
        } else {
            html += `<div class="table-container"><table>
                <thead><tr>
                    <th scope="col">Name</th><th scope="col">Pattern</th><th scope="col">Match Type</th>
                    <th scope="col">Scope</th><th scope="col">Decision</th><th scope="col">Priority</th><th scope="col">Active</th><th scope="col">Actions</th>
                </tr></thead><tbody>`;
            for (const r of rules) {
                html += `<tr>
                    <td><strong>${escapeHtml(r.name)}</strong></td>
                    <td><code>${escapeHtml(r.pattern)}</code></td>
                    <td>${escapeHtml(r.rule_type)}</td>
                    <td>${escapeHtml(r.direction)} · ${r.bank_account_id ? `register ${r.bank_account_id}` : 'all registers'}<br><small>${escapeHtml(r.match_field)}</small></td>
                    <td>${escapeHtml(r.intent || 'category hint')} · account ${r.account_id || '—'}<br><small>${escapeHtml(r.class_resolution || 'class unresolved')}</small></td>
                    <td>${r.priority}</td>
                    <td>${r.is_active ? 'Yes' : 'No'}</td>
                    <td class="actions">
                        <button class="btn btn-sm btn-secondary" onclick="BankRulesPage.showForm(${r.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="BankRulesPage.deleteRule(${r.id})">Delete</button>
                    </td>
                </tr>`;
            }
            html += '</tbody></table></div>';
        }
        return html;
    },

    async showForm(id = null, preset = null) {
        let rule = preset || {
            name: '', pattern: '', account_id: '', vendor_id: '', customer_id: '', bank_account_id: '', class_id: '',
            rule_type: 'contains', match_field: 'raw', direction: 'any', minimum_amount: '', maximum_amount: '',
            intent: '', posting_route: '', counterparty_role: '', counterparty_resolution: '', class_resolution: '',
            priority: 0, is_active: true,
        };
        if (id) rule = await API.get(`/bank-rules/${id}`);

        const [accounts, registers, customers, vendors, classes] = await Promise.all([
            API.get('/accounts'), API.get('/banking/accounts'), API.get('/customers?active_only=true'),
            API.get('/vendors?active_only=true'), API.get('/classes'),
        ]);
        const selected = (value, current) => value === current ? 'selected' : '';
        const acctOpts = accounts
            .filter(a => ['expense','income','asset','liability','cogs'].includes(a.account_type))
            .map(a => `<option value="${a.id}" ${rule.account_id==a.id?'selected':''}>${escapeHtml(a.account_number)} - ${escapeHtml(a.name)}</option>`).join('');
        const registerOpts = registers.map(a => `<option value="${a.id}" ${rule.bank_account_id==a.id?'selected':''}>${escapeHtml(a.name)}</option>`).join('');
        const customerOpts = customers.map(a => `<option value="${a.id}" ${rule.customer_id==a.id?'selected':''}>${escapeHtml(a.name)}</option>`).join('');
        const vendorOpts = vendors.map(a => `<option value="${a.id}" ${rule.vendor_id==a.id?'selected':''}>${escapeHtml(a.name)}</option>`).join('');
        const classOpts = classes.filter(a => !a.is_archived).map(a => `<option value="${a.id}" ${rule.class_id==a.id?'selected':''}>${escapeHtml(a.name)}</option>`).join('');

        openModal(id ? 'Edit Bank Rule' : 'New Bank Rule', `
            <form onsubmit="BankRulesPage.save(event, ${id})">
                <div class="form-grid">
                    <div class="form-group"><label>Rule Name *</label>
                        <input name="name" required value="${escapeHtml(rule.name)}"></div>
                    <div class="form-group"><label>Payee Pattern *</label>
                        <input name="pattern" required value="${escapeHtml(rule.pattern)}" placeholder="e.g. AMZN or Amazon"></div>
                    <div class="form-group"><label>Match Text</label>
                        <select name="match_field"><option value="raw" ${selected('raw', rule.match_field)}>Raw statement text</option><option value="normalized" ${selected('normalized', rule.match_field)}>Normalized counterparty</option></select></div>
                    <div class="form-group"><label>Match Type</label>
                        <select name="rule_type">
                            <option value="contains" ${rule.rule_type==='contains'?'selected':''}>Contains</option>
                            <option value="starts_with" ${rule.rule_type==='starts_with'?'selected':''}>Starts With</option>
                            <option value="exact" ${rule.rule_type==='exact'?'selected':''}>Exact Match</option>
                        </select></div>
                    <div class="form-group"><label>Register</label><select name="bank_account_id"><option value="">All registers</option>${registerOpts}</select></div>
                    <div class="form-group"><label>Direction</label><select name="direction"><option value="any" ${selected('any', rule.direction)}>Any</option><option value="deposit" ${selected('deposit', rule.direction)}>Deposit</option><option value="withdrawal" ${selected('withdrawal', rule.direction)}>Withdrawal</option></select></div>
                    <div class="form-group"><label>Minimum Amount</label><input name="minimum_amount" type="number" min="0" step="0.01" value="${rule.minimum_amount ?? ''}"></div>
                    <div class="form-group"><label>Maximum Amount</label><input name="maximum_amount" type="number" min="0" step="0.01" value="${rule.maximum_amount ?? ''}"></div>
                    <div class="form-group"><label>Category Account</label>
                        <select name="account_id"><option value="">-- None --</option>${acctOpts}</select></div>
                    <div class="form-group"><label>Intent</label><select name="intent"><option value="">No intent</option>${['direct_expense','direct_income','customer_payment','bill_payment','owner_contribution','owner_draw','loan_proceeds','loan_payment','investment_activity','reimbursement','unknown'].map(v => `<option value="${v}" ${selected(v, rule.intent)}>${escapeHtml(v.replaceAll('_',' '))}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Posting Route</label><select name="posting_route"><option value="">No route</option>${['direct','customer_payment','bill_payment','hold'].map(v => `<option value="${v}" ${selected(v, rule.posting_route)}>${escapeHtml(v.replaceAll('_',' '))}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Counterparty Role</label><select name="counterparty_role"><option value="">Unspecified</option>${['payer','payee','not_applicable'].map(v => `<option value="${v}" ${selected(v, rule.counterparty_role)}>${escapeHtml(v)}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Counterparty Decision</label><select name="counterparty_resolution"><option value="">Unspecified</option>${['unresolved','text_only','customer','vendor','not_applicable'].map(v => `<option value="${v}" ${selected(v, rule.counterparty_resolution)}>${escapeHtml(v.replaceAll('_',' '))}</option>`).join('')}</select></div>
                    <div class="form-group"><label>${T('Customer')}</label><select name="customer_id"><option value="">-- None --</option>${customerOpts}</select></div>
                    <div class="form-group"><label>Vendor</label><select name="vendor_id"><option value="">-- None --</option>${vendorOpts}</select></div>
                    <div class="form-group"><label>${T('Class')} Decision</label><select name="class_resolution"><option value="">Unspecified</option>${['unresolved','personal_no_class','assigned','not_applicable'].map(v => `<option value="${v}" ${selected(v, rule.class_resolution)}>${escapeHtml(v.replaceAll('_',' '))}</option>`).join('')}</select></div>
                    <div class="form-group"><label>${T('Class')}</label><select name="class_id"><option value="">-- None --</option>${classOpts}</select></div>
                    <div class="form-group"><label>Priority</label>
                        <input name="priority" type="number" value="${rule.priority}" title="Higher = checked first"></div>
                    <div class="form-group"><label>Active</label>
                        <select name="is_active">
                            <option value="true" ${rule.is_active !== false ? 'selected' : ''}>Yes</option>
                            <option value="false" ${rule.is_active === false ? 'selected' : ''}>No</option>
                        </select></div>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">${id ? 'Update' : 'Create'} Rule</button>
                </div>
            </form>`);
    },

    async save(e, id) {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target).entries());
        for (const field of ['account_id','vendor_id','customer_id','bank_account_id','class_id']) {
            data[field] = data[field] ? parseInt(data[field]) : null;
        }
        for (const field of ['minimum_amount','maximum_amount']) data[field] = data[field] || null;
        for (const field of ['intent','posting_route','counterparty_role','counterparty_resolution','class_resolution']) data[field] = data[field] || null;
        data.priority = parseInt(data.priority) || 0;
        data.is_active = data.is_active === 'true';
        try {
            if (id) { await API.put(`/bank-rules/${id}`, data); toast('Rule updated'); }
            else { await API.post('/bank-rules', data); toast('Rule created'); }
            closeModal();
            App.navigate('#/bank-rules');
        } catch (err) { toast(err.message, 'error'); }
    },

    async deleteRule(id) {
        if (!confirm('Delete this rule?')) return;
        try {
            await API.del(`/bank-rules/${id}`);
            toast('Rule deleted');
            App.navigate('#/bank-rules');
        } catch (err) { toast(err.message, 'error'); }
    },

    async applyAll() {
        try {
            const result = await API.post('/bank-rules/apply');
            toast(`Matched ${result.matched}; created ${result.proposed} review proposal(s)`);
        } catch (err) { toast(err.message, 'error'); }
    },
};
