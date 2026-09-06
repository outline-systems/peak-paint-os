from pathlib import Path
import re

BAY = Path('/tmp/baywide.html').read_text(errors='ignore')


def adapt(s: str) -> str:
    replacements = [
        ('https://outline-systems.github.io/baywide-dingos-os/', 'https://outline-systems.github.io/peak-paint-os/'),
        ('BAYWIDE DINGOS', 'PEAK PAINTING & DECORATING LTD'),
        ('Baywide Dingos OS', 'Peak Paint OS'),
        ('Baywide Dingos', 'Peak Painting'),
        ('Baywide OS', 'Peak Paint OS'),
        ("Baywide's", "Peak's"),
        ('Baywide H&S Policy', 'Peak H&S Policy'),
        ('No Baywide H&amp;S policy', 'No Peak H&amp;S policy'),
        ('Baywide H&amp;S', 'Peak H&amp;S'),
        ('Baywide Red', 'Peak Red'),
        ('Baywide Blue', 'Peak Blue'),
        ('aria-label=\\"Baywide Dingos OS\\"', 'aria-label=\\"Peak Paint OS\\"'),
    ]
    for a, b in replacements:
        s = s.replace(a, b)
    s = s.replace("'Baywide · ", "'Peak · ").replace('"Baywide · ', '"Peak · ')
    return s


def sc_occurrences(text: str, key: str):
    patterns = [
        f'<sc-if value=\\"{{{{ {key} }}}}\\">',
        f'<sc-if value="{{{{ {key} }}}}">',
    ]
    out = []
    for p in patterns:
        out += [(m.start(), p) for m in re.finditer(re.escape(p), text)]
    return sorted(out)


def settings_block(text: str, prefer_marker: bool):
    starts = sc_occurrences(text, 'hqSettings')
    if not starts:
        raise RuntimeError('Settings start not found')
    if prefer_marker:
        marker = 'Company details &amp; document template'
        mp = text.find(marker)
        if mp < 0:
            raise RuntimeError('Baywide modular Settings marker not found')
        before = [x for x in starts if x[0] < mp]
        if not before:
            raise RuntimeError('No Settings start before modular marker')
        st = before[-1][0]
    else:
        # Peak only has one active template block; choose the first source block.
        st = starts[0][0]
    ends = [x[0] for x in sc_occurrences(text, 'isHQ') if x[0] > st]
    if not ends:
        raise RuntimeError('Settings end not found')
    en = ends[0]
    return st, en, text[st:en]


def scan_method(text: str, name: str):
    matches = list(re.finditer(r'(?m)^[ \t]{2}' + re.escape(name) + r'\s*\(', text))
    if not matches:
        return None
    m = matches[-1]
    start = m.start()
    i = m.end() - 1
    par = 0
    quote = None
    esc = False
    line = False
    block = False
    open_brace = None
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ''
        if line:
            if c == '\n':
                line = False
            i += 1
            continue
        if block:
            if c == '*' and n == '/':
                block = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            i += 1
            continue
        if c == '/' and n == '/':
            line = True
            i += 2
            continue
        if c == '/' and n == '*':
            block = True
            i += 2
            continue
        if c == '(':
            par += 1
        elif c == ')':
            par -= 1
            if par == 0:
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1
                if j < len(text) and text[j] == '{':
                    open_brace = j
                    break
        i += 1
    if open_brace is None:
        return None

    depth = 0
    quote = None
    esc = False
    line = False
    block = False
    i = open_brace
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ''
        if line:
            if c == '\n':
                line = False
            i += 1
            continue
        if block:
            if c == '*' and n == '/':
                block = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            i += 1
            continue
        if c == '/' and n == '/':
            line = True
            i += 2
            continue
        if c == '/' and n == '*':
            block = True
            i += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(text) and text[end] in ' \t':
                    end += 1
                if end < len(text) and text[end] == '\n':
                    end += 1
                return start, end, text[start:end]
        i += 1
    return None


def replace_or_insert_method(text: str, name: str, source_method: str):
    current = scan_method(text, name)
    source_method = adapt(source_method)
    if current:
        a, b, _ = current
        return text[:a] + source_method + text[b:]
    render = scan_method(text, 'render')
    if not render:
        raise RuntimeError(f'render() insertion anchor not found for {name}')
    a = render[0]
    return text[:a] + source_method + '\n' + text[a:]


# Current Baywide behavior methods.
method_names = []
for m in re.finditer(r'(?m)^[ \t]{2}([A-Za-z_$][\w$]*)\s*\(', BAY):
    name = m.group(1)
    if name not in method_names:
        method_names.append(name)
BAY_METHODS = {}
for name in method_names:
    found = scan_method(BAY, name)
    if found:
        BAY_METHODS[name] = found[2]

ROOTS = {
    'prepareCompanyLogo', 'companyLogoUpload', 'companyLogoRemove', '__policyRenderPdf', 'hsPolicyUpload', 'hsPolicyRemove',
    '__crewPhotoData', 'crewPhotoUpload', 'crewPhotoRemove',
    'gcalSetClient', 'gcalSetAuto', 'gcalSelectCalendar', '__gcalReady', '__gcalScript', '__gcalApi', 'gcalConnect', 'gcalDisconnect', 'gcalLoadCalendars',
    '__gcalRef', '__gcalSaveRef', '__gcalDropRef', '__localIso', '__hoursSpan', '__crewEmails', '__projectByCode', '__scheduleIntervalsFor', '__localClashes',
    '__gcalProjectPayload', '__gcalTaskPayload', '__gcalUpsert', 'gcalDelete', 'gcalSyncProject', 'gcalSyncTask', 'gcalSyncAll', 'gcalCheckAvailability',
    'crewTaskNewHQ', 'crewTaskEditHQ', 'crewTaskAddHQ', 'crewTaskToggle', 'crewTaskDel',
    '__brandColor', '__brandOnColor', 'setBrandColor', '__docColor', 'setDocColor', 'setDocColorSync', '__mixHex', '__docThemeMap', '__retintInlineStyles', '__applyDocThemeTo', '__applyTheme',
}
missing = sorted(n for n in ROOTS if n not in BAY_METHODS)
if missing:
    raise RuntimeError('Missing Baywide methods: ' + ', '.join(missing))


def patch_one(text: str, label: str):
    # 1. Replace only Peak's Settings template with Baywide's current modular Settings template.
    _, _, bay_settings = settings_block(BAY, True)
    ps, pe, _ = settings_block(text, False)
    text = text[:ps] + adapt(bay_settings) + text[pe:]

    # 2. State defaults. Keep Peak's existing schema version so live customer state is not reset.
    state_pos = text.rfind('\n  state = {')
    if state_pos < 0:
        raise RuntimeError(f'{label}: state block missing')
    tail = text[state_pos:]
    theme_anchor = "theme: 'dark', peakSchema: 4,"
    if theme_anchor in tail:
        tail = tail.replace(theme_anchor, "theme: 'dark', brandColor: '#E1272A', docColor: '#E1272A', docColorSync: false, peakSchema: 4,", 1)
    elif 'brandColor:' not in tail[:5000]:
        raise RuntimeError(f'{label}: theme/schema anchor missing')

    task_anchor = 'crewTasks: [], leaveReqs: [], crewNotes: [], roosters: [],'
    if task_anchor in tail and 'hqTaskWho:' not in tail[:16000]:
        tail = tail.replace(
            task_anchor,
            task_anchor + "\n    hqTaskWho: '', hqTaskJob: '', hqTaskText: '', hqTaskDue: '', hqTaskDate: '', hqTaskStart: '07:30', hqTaskEnd: '16:30', hqTaskPriority: 'Normal', hqTaskEditing: null, hqTaskFlash: '', hqTaskCalCheck: '',",
            1,
        )

    co_match = re.search(r"\n\s*co:\s*\{[^\n]*name:\s*'PEAK PAINTING & DECORATING LTD'[^\n]*\},", tail)
    if co_match and 'coDraft:' not in tail[co_match.start():co_match.start() + 1800]:
        line = co_match.group(0)
        obj = line[line.find('{'):line.rfind('}') + 1]
        if 'logo:' not in obj:
            obj = obj[:-1] + ", logo: '', logoName: '', hsPolicy: null, _ts: 0 }"
        replacement = '\n    co: ' + obj + ',\n    coDraft: ' + obj + ", coFlash: '', coLogoMsg: '', coPolicyMsg: '',"
        tail = tail[:co_match.start()] + replacement + tail[co_match.end():]
    elif 'coDraft:' not in tail:
        raise RuntimeError(f'{label}: company state anchor missing')

    crew_match = re.search(r'\n\s*crew:\s*\[[^\n]*\],\s*crewNext:\s*5,', tail)
    if crew_match:
        crew_line = crew_match.group(0)
        crew_line = re.sub(r"pin:\s*([^,}]+)\s*}", r"pin: \1, googleEmail: '', photo: '' }", crew_line)
        tail = tail[:crew_match.start()] + crew_line + tail[crew_match.end():]

    if 'gcalClientId:' not in tail[:35000]:
        crew_match = re.search(r'\n\s*crew:\s*\[[^\n]*\],\s*crewNext:\s*5,', tail)
        if not crew_match:
            raise RuntimeError(f'{label}: crew seed anchor missing for Calendar state')
        calendar_state = "\n    gcalClientId: '', gcalCalendarId: 'primary', gcalCalendarName: 'Primary calendar', gcalCalendars: [], gcalAutoPublish: true, gcalEventIds: { project: {}, task: {} }, gcalStatus: 'Not connected', gcalBusy: false, gcalLastSync: '', pjCalCheck: '',"
        tail = tail[:crew_match.end()] + calendar_state + tail[crew_match.end():]
    text = text[:state_pos] + tail

    # 3. Company edits are staged until Save company details, exactly like current Baywide behavior.
    old_cof = r"const coF = \(k\) => \(e\) => this\.setState\(s => \(\{ co: \{ \.\.\.s\.co, \[k\]: e\.target\.value \} \}\)\);"
    new_cof = "const coF = (k) => (e) => this.setState(s => ({ coDraft: { ...(s.coDraft || s.co || {}), [k]: e.target.value }, coFlash: '', coLogoMsg: '' }));"
    text, changed = re.subn(old_cof, new_cof, text, count=1)
    if changed == 0 and new_cof not in text:
        raise RuntimeError(f'{label}: coF edit anchor missing')

    # 4. Local render helpers for saved/draft logo and tender policy.
    co_pos = text.rfind('const coF = (k) =>')
    if co_pos < 0:
        raise RuntimeError(f'{label}: coF position missing')
    if '__coSavedPolicy' not in text[max(0, co_pos - 3500):co_pos]:
        bay_cof = BAY.rfind('const coF = (k) =>')
        var_anchor = BAY.rfind('var __coSaved', 0, bay_cof)
        if var_anchor < 0:
            raise RuntimeError('Baywide company render variables missing')
        vars_source = adapt(BAY[var_anchor:bay_cof])
        text = text[:co_pos] + vars_source + text[co_pos:]

    # 5. Add Baywide company settings bindings while preserving Peak quote/invoice bindings.
    co_binding = text.rfind('      co: S.co,')
    if co_binding < 0:
        raise RuntimeError(f'{label}: return company binding missing')
    end = co_binding + len('      co: S.co,')
    if 'coEdit:' not in text[co_binding:co_binding + 8500]:
        company_bind = " coEdit: (S.coDraft || S.co), brandName: String(((S.co || {}).name) || 'PEAK PAINTING & DECORATING LTD'), brandLogo: String(((S.co || {}).logo) || ''), brandLogoShow: !!String(((S.co || {}).logo) || ''), brandLogoFallback: !String(((S.co || {}).logo) || ''), brandLogoDraft: String(((S.coDraft || S.co || {}).logo) || ''), brandLogoDraftShow: !!String(((S.coDraft || S.co || {}).logo) || ''), brandLogoDraftFallback: !String(((S.coDraft || S.co || {}).logo) || ''), coLogoMsg: S.coLogoMsg || '', coLogoMsgShow: !!S.coLogoMsg, companyLogoUpload: (e) => this.companyLogoUpload(e), removeCompanyLogo: () => this.companyLogoRemove(), hsPolicyHas: !!(__coEditPolicy && (__coEditPolicy.pages || []).length), hsPolicyNone: !(__coEditPolicy && (__coEditPolicy.pages || []).length), hsPolicyName: (__coEditPolicy && __coEditPolicy.name) || '', hsPolicyMeta: (__coEditPolicy ? (((__coEditPolicy.pageCount || (__coEditPolicy.pages || []).length || 0) + ' page' + (((__coEditPolicy.pageCount || (__coEditPolicy.pages || []).length || 0) === 1) ? '' : 's') + ' · ' + this.fmtKB(__coEditPolicy.size || 0))) : ''), hsPolicyPages: hsPolicyPages, hsPolicyExportHas: hsPolicyPages.length > 0, hsPolicyExportName: (__coSavedPolicy && __coSavedPolicy.name) || 'Peak H&S Policy', hsPolicyIndexLabel: hsPolicyPages.length ? 'Appendix A' : 'Not attached', hsPolicyUpload: (e) => this.hsPolicyUpload(e), hsPolicyRemove: () => this.hsPolicyRemove(), coPolicyMsg: S.coPolicyMsg || '', coPolicyMsgShow: !!S.coPolicyMsg, coFlash: S.coFlash || '', coFlashShow: !!S.coFlash, saveCompany: () => { var next = Object.assign({}, (this.state.coDraft || this.state.co || {}), { _ts: Date.now() }); this.setState({ co: next, coDraft: Object.assign({}, next), coFlash: 'Saved and applied across the app.', coLogoMsg: next.logo ? 'Logo saved and applied across the app.' : '' }, () => { try { document.title = (next.name || 'Peak Paint OS') + ' · Peak Paint OS'; } catch (e) {} try { this.__peakSave(); } catch (e) {} try { this.syncPush(); } catch (e) {} var self = this; setTimeout(function () { if (self.state.coFlash) self.setState({ coFlash: '' }); }, 3200); }); },"
        text = text[:end] + company_bind + text[end:]

    # 6. HQ crew-task, profile-photo, Google/work-email and Calendar render bindings.
    b_start = BAY.rfind('      hqTaskCrewOpts:')
    b_end = BAY.find('      npCrewChips:', b_start)
    if b_start < 0 or b_end < 0:
        raise RuntimeError('Baywide crew/Calendar render bindings missing')
    crew_bindings = adapt(BAY[b_start:b_end])
    p_start = text.rfind('      crewRows:')
    p_end = text.find('      npCrewChips:', p_start)
    if p_start < 0 or p_end < 0:
        raise RuntimeError(f'{label}: Peak crew binding anchor missing')
    text = text[:p_start] + crew_bindings + text[p_end:]

    # 7. Current Baywide Look & Feel and Recently Deleted bindings.
    b_plan = BAY.rfind('      planFilesView:')
    b_look = BAY.rfind('      brandColor:', 0, b_plan)
    if b_look < 0 or b_plan < 0:
        raise RuntimeError('Baywide Look & Feel binding segment missing')
    look_bindings = adapt(BAY[b_look:b_plan]).replace('Modern — Jakarta / Barlow', 'Peak — Jakarta / Barlow')
    p_plan = text.rfind('      planFilesView:')
    p_look = text.rfind('      cornerOpts:', 0, p_plan)
    if p_look < 0 or p_plan < 0:
        raise RuntimeError(f'{label}: Peak Look & Feel binding anchor missing')
    text = text[:p_look] + look_bindings + text[p_plan:]

    # 8. Port current Baywide behavior methods and missing transitive helpers.
    peak_names = {m.group(1) for m in re.finditer(r'(?m)^[ \t]{2}([A-Za-z_$][\w$]*)\s*\(', text)}
    selected = set(ROOTS)
    queue = list(ROOTS)
    while queue:
        name = queue.pop()
        source = BAY_METHODS.get(name, '')
        for ref in re.findall(r'this\.([A-Za-z_$][\w$]*)\s*\(', source):
            if ref in BAY_METHODS and ref not in selected and ref not in peak_names:
                selected.add(ref)
                queue.append(ref)
    for name in sorted(selected):
        if name in ROOTS or name not in peak_names:
            text = replace_or_insert_method(text, name, BAY_METHODS[name])

    # 9. Persist/sync the company object and brand/document look; keep Peak's existing workspace.
    sync = scan_method(text, '__syncKeys')
    if not sync:
        raise RuntimeError(f'{label}: __syncKeys missing')
    a, b, body = sync
    additions = ['co', 'brandColor', 'docColor', 'docColorSync']
    close = body.rfind(']')
    if close < 0:
        raise RuntimeError(f'{label}: __syncKeys return list missing')
    for key in additions:
        if f"'{key}'" not in body:
            body = body[:close] + ", '" + key + "'" + body[close:]
            close = body.rfind(']')
    text = text[:a] + body + text[b:]

    merge = scan_method(text, '__mergeState')
    if not merge:
        raise RuntimeError(f'{label}: __mergeState missing')
    a, b, body = merge
    arr_match = re.search(r"\['quotes'.*?'clockEvents'\]\.forEach", body, re.S)
    if arr_match and "'crewTasks'" not in arr_match.group(0):
        old = arr_match.group(0)
        new = old.replace("'clockEvents'", "'clockEvents', 'crewTasks', 'leaveReqs', 'crewNotes', 'roosters', 'contacts', 'recycle'")
        body = body[:arr_match.start()] + new + body[arr_match.end():]
    if 'remote.co && typeof remote.co' not in body:
        pos = body.rfind('return out;')
        if pos < 0:
            raise RuntimeError(f'{label}: merge return missing')
        extra = "['pkCorner','pkType','brandColor','docColor','docColorSync'].forEach(function (k) { if (remote[k] !== undefined) out[k] = remote[k]; }); if (remote.co && typeof remote.co === 'object') { var lc = s.co || {}, rc = remote.co || {}; out.co = ((+lc._ts || 0) > (+rc._ts || 0)) ? Object.assign({}, rc, lc) : Object.assign({}, lc, rc); out.coDraft = Object.assign({}, out.co); } "
        body = body[:pos] + extra + body[pos:]
    text = text[:a] + body + text[b:]

    # Safety / parity checks.
    required = [
        'Company details &amp; document template', 'Crew &amp; employees', 'Integrations', 'Look &amp; feel', 'Recently deleted',
        'Connect Google Calendar', 'Google / work email', 'Tender H&amp;S policy', 'Save company details',
        'companyLogoUpload', 'hsPolicyUpload', 'crewPhotoUpload', 'gcalConnect', 'setBrandColor', 'coDraft:',
        "ws: 'peak-hb'", 'PEAK PAINTING & DECORATING LTD', 'Peak Painting HB SOR 2026', 'Interior', 'Exterior',
    ]
    for token in required:
        if token not in text:
            raise RuntimeError(f'{label}: required token missing: {token}')
    if "ws: 'baywide-dingos-os'" in text:
        raise RuntimeError(f'{label}: Baywide workspace leaked into Peak')
    _, _, panel = settings_block(text, True)
    for bad in ['Baywide Dingos', 'Baywide OS', "Baywide's"]:
        if bad in panel:
            raise RuntimeError(f'{label}: Baywide customer branding remains in Settings: {bad}')
    return text


def main():
    targets = ['index.html']
    if Path('preview/index.html').exists():
        targets.append('preview/index.html')
    for target in targets:
        p = Path(target)
        old = p.read_text(errors='ignore')
        new = patch_one(old, target)
        p.write_text(new)
        print(f'{target}: {len(old)} -> {len(new)} chars')


if __name__ == '__main__':
    main()
