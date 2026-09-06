from pathlib import Path
import re

BAY = Path('/tmp/baywide.html').read_text(errors='ignore')


def adapt(s):
    for a, b in [
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
    ]:
        s = s.replace(a, b)
    return s.replace("'Baywide · ", "'Peak · ").replace('"Baywide · ', '"Peak · ')


def sc_positions(text, key):
    out = []
    for pat in [f'<sc-if value=\\"{{{{ {key} }}}}\\">', f'<sc-if value="{{{{ {key} }}}}">']:
        out.extend(m.start() for m in re.finditer(re.escape(pat), text))
    return sorted(out)


def settings_block(text, baywide=False):
    starts = sc_positions(text, 'hqSettings')
    if not starts:
        raise RuntimeError('Settings block start missing')
    if baywide:
        marker = text.find('Company details &amp; document template')
        if marker < 0:
            raise RuntimeError('Baywide modular Settings marker missing')
        starts = [p for p in starts if p < marker]
        if not starts:
            raise RuntimeError('Baywide Settings start missing')
        start = starts[-1]
    else:
        start = starts[0]
    ends = [p for p in sc_positions(text, 'isHQ') if p > start]
    if not ends:
        raise RuntimeError('Settings block end missing')
    end = ends[0]
    return start, end, text[start:end]


def method_spans(text):
    # The generated app stores its source with literal \\n separators, so accept both real and escaped newlines.
    pat = re.compile(r'(?:^|\n|\\n)([ \t]{2})([A-Za-z_$][\w$]*)\s*\(')
    matches = list(pat.finditer(text))
    spans = []
    for i, m in enumerate(matches):
        start = m.start(1)
        end = matches[i + 1].start(1) if i + 1 < len(matches) else len(text)
        spans.append((m.group(2), start, end, text[start:end]))
    return spans


def method_map(text):
    out = {}
    for name, a, b, src in method_spans(text):
        out[name] = (a, b, src)
    return out


BAY_METHODS = {name: src for name, _, _, src in method_spans(BAY)}
ROOTS = {
    'prepareCompanyLogo', 'companyLogoUpload', 'companyLogoRemove', '__policyRenderPdf', 'hsPolicyUpload', 'hsPolicyRemove',
    '__crewPhotoData', 'crewPhotoUpload', 'crewPhotoRemove',
    'gcalSetClient', 'gcalSetAuto', 'gcalSelectCalendar', '__gcalReady', '__gcalScript', '__gcalApi', 'gcalConnect', 'gcalDisconnect', 'gcalLoadCalendars',
    '__gcalRef', '__gcalSaveRef', '__gcalDropRef', '__localIso', '__hoursSpan', '__crewEmails', '__projectByCode', '__scheduleIntervalsFor', '__localClashes',
    '__gcalProjectPayload', '__gcalTaskPayload', '__gcalUpsert', 'gcalDelete', 'gcalSyncProject', 'gcalSyncTask', 'gcalSyncAll', 'gcalCheckAvailability',
    'crewTaskNewHQ', 'crewTaskEditHQ', 'crewTaskAddHQ', 'crewTaskToggle', 'crewTaskDel',
    '__brandColor', '__brandOnColor', 'setBrandColor', '__docColor', 'setDocColor', 'setDocColorSync', '__mixHex', '__docThemeMap', '__retintInlineStyles', '__applyDocThemeTo', '__applyTheme',
}
missing = sorted(ROOTS.difference(BAY_METHODS))
if missing:
    raise RuntimeError('Baywide method extraction still missing: ' + ', '.join(missing))


def replace_or_insert_method(text, name, source):
    cur = method_map(text)
    src = adapt(source)
    if name in cur:
        a, b, _ = cur[name]
        return text[:a] + src + text[b:]
    if 'render' not in cur:
        raise RuntimeError('render() missing while inserting ' + name)
    a = cur['render'][0]
    return text[:a] + src + text[a:]


def patch_one(text, label):
    sep = '\\n' if '\\n  state = {' in text else '\n'

    # Exact Baywide modular Settings markup; only company/trade naming is adapted.
    _, _, bw_settings = settings_block(BAY, True)
    ps, pe, _ = settings_block(text, False)
    text = text[:ps] + adapt(bw_settings) + text[pe:]

    state_pos = text.rfind('state = {')
    if state_pos < 0:
        raise RuntimeError(label + ': state missing')
    tail = text[state_pos:]

    anchor = "theme: 'dark', peakSchema: 4,"
    if anchor in tail:
        tail = tail.replace(anchor, "theme: 'dark', brandColor: '#E1272A', docColor: '#E1272A', docColorSync: false, peakSchema: 4,", 1)
    elif 'brandColor:' not in tail[:5000]:
        raise RuntimeError(label + ': theme anchor missing')

    task_anchor = 'crewTasks: [], leaveReqs: [], crewNotes: [], roosters: [],'
    if task_anchor in tail and 'hqTaskWho:' not in tail[:18000]:
        tail = tail.replace(task_anchor, task_anchor + sep + "    hqTaskWho: '', hqTaskJob: '', hqTaskText: '', hqTaskDue: '', hqTaskDate: '', hqTaskStart: '07:30', hqTaskEnd: '16:30', hqTaskPriority: 'Normal', hqTaskEditing: null, hqTaskFlash: '', hqTaskCalCheck: '',", 1)

    co = re.search(r"co:\s*\{[^{}]*name:\s*'PEAK PAINTING & DECORATING LTD'[^{}]*\},", tail)
    if co and 'coDraft:' not in tail[co.start():co.start() + 2200]:
        raw = co.group(0)
        obj = raw[raw.find('{'):raw.rfind('}') + 1]
        if 'logo:' not in obj:
            obj = obj[:-1] + ", logo: '', logoName: '', hsPolicy: null, _ts: 0 }"
        repl = 'co: ' + obj + ',' + sep + "    coDraft: " + obj + ", coFlash: '', coLogoMsg: '', coPolicyMsg: '',"
        tail = tail[:co.start()] + repl + tail[co.end():]
    elif 'coDraft:' not in tail:
        raise RuntimeError(label + ': company state anchor missing')

    crew = re.search(r'crew:\s*\[(.*?)\],\s*crewNext:\s*5,', tail, re.S)
    if crew:
        src = crew.group(0)
        src = re.sub(r"pin:\s*([^,}]+)\s*}", r"pin: \1, googleEmail: '', photo: '' }", src)
        tail = tail[:crew.start()] + src + tail[crew.end():]

    if 'gcalClientId:' not in tail[:40000]:
        crew = re.search(r'crew:\s*\[(.*?)\],\s*crewNext:\s*5,', tail, re.S)
        if not crew:
            raise RuntimeError(label + ': crew anchor missing')
        cal = sep + "    gcalClientId: '', gcalCalendarId: 'primary', gcalCalendarName: 'Primary calendar', gcalCalendars: [], gcalAutoPublish: true, gcalEventIds: { project: {}, task: {} }, gcalStatus: 'Not connected', gcalBusy: false, gcalLastSync: '', pjCalCheck: '',"
        tail = tail[:crew.end()] + cal + tail[crew.end():]

    text = text[:state_pos] + tail

    # Staged Company Details save behavior.
    old = r"const coF = \(k\) => \(e\) => this\.setState\(s => \(\{ co: \{ \.\.\.s\.co, \[k\]: e\.target\.value \} \}\)\);"
    new = "const coF = (k) => (e) => this.setState(s => ({ coDraft: { ...(s.coDraft || s.co || {}), [k]: e.target.value }, coFlash: '', coLogoMsg: '' }));"
    text, n = re.subn(old, new, text, count=1)
    if n == 0 and new not in text:
        raise RuntimeError(label + ': staged company edit function missing')

    cof = text.rfind('const coF = (k) =>')
    if cof < 0:
        raise RuntimeError(label + ': coF missing')
    if '__coSavedPolicy' not in text[max(0, cof - 5000):cof]:
        bw_cof = BAY.rfind('const coF = (k) =>')
        va = BAY.rfind('var __coSaved', 0, bw_cof)
        if va < 0:
            raise RuntimeError('Baywide company render locals missing')
        text = text[:cof] + adapt(BAY[va:bw_cof]) + text[cof:]

    bind = text.rfind('      co: S.co,')
    if bind < 0:
        raise RuntimeError(label + ': company binding missing')
    end = bind + len('      co: S.co,')
    if 'coEdit:' not in text[bind:bind + 9000]:
        extra = " coEdit: (S.coDraft || S.co), brandName: String(((S.co || {}).name) || 'PEAK PAINTING & DECORATING LTD'), brandLogo: String(((S.co || {}).logo) || ''), brandLogoShow: !!String(((S.co || {}).logo) || ''), brandLogoFallback: !String(((S.co || {}).logo) || ''), brandLogoDraft: String(((S.coDraft || S.co || {}).logo) || ''), brandLogoDraftShow: !!String(((S.coDraft || S.co || {}).logo) || ''), brandLogoDraftFallback: !String(((S.coDraft || S.co || {}).logo) || ''), coLogoMsg: S.coLogoMsg || '', coLogoMsgShow: !!S.coLogoMsg, companyLogoUpload: (e) => this.companyLogoUpload(e), removeCompanyLogo: () => this.companyLogoRemove(), hsPolicyHas: !!(__coEditPolicy && (__coEditPolicy.pages || []).length), hsPolicyNone: !(__coEditPolicy && (__coEditPolicy.pages || []).length), hsPolicyName: (__coEditPolicy && __coEditPolicy.name) || '', hsPolicyMeta: (__coEditPolicy ? (((__coEditPolicy.pageCount || (__coEditPolicy.pages || []).length || 0) + ' page' + (((__coEditPolicy.pageCount || (__coEditPolicy.pages || []).length || 0) === 1) ? '' : 's') + ' · ' + this.fmtKB(__coEditPolicy.size || 0))) : ''), hsPolicyPages: hsPolicyPages, hsPolicyExportHas: hsPolicyPages.length > 0, hsPolicyExportName: (__coSavedPolicy && __coSavedPolicy.name) || 'Peak H&S Policy', hsPolicyIndexLabel: hsPolicyPages.length ? 'Appendix A' : 'Not attached', hsPolicyUpload: (e) => this.hsPolicyUpload(e), hsPolicyRemove: () => this.hsPolicyRemove(), coPolicyMsg: S.coPolicyMsg || '', coPolicyMsgShow: !!S.coPolicyMsg, coFlash: S.coFlash || '', coFlashShow: !!S.coFlash, saveCompany: () => { var next = Object.assign({}, (this.state.coDraft || this.state.co || {}), { _ts: Date.now() }); this.setState({ co: next, coDraft: Object.assign({}, next), coFlash: 'Saved and applied across the app.', coLogoMsg: next.logo ? 'Logo saved and applied across the app.' : '' }, () => { try { document.title = (next.name || 'Peak Paint OS') + ' · Peak Paint OS'; } catch (e) {} try { this.__peakSave(); } catch (e) {} try { this.syncPush(); } catch (e) {} var self = this; setTimeout(function () { if (self.state.coFlash) self.setState({ coFlash: '' }); }, 3200); }); },"
        text = text[:end] + extra + text[end:]

    # Crew tasks, profile photos, Google email and Calendar bindings.
    bs = BAY.rfind('      hqTaskCrewOpts:')
    be = BAY.find('      npCrewChips:', bs)
    if bs < 0 or be < 0:
        raise RuntimeError('Baywide crew binding block missing')
    ps = text.rfind('      crewRows:')
    pe = text.find('      npCrewChips:', ps)
    if ps < 0 or pe < 0:
        raise RuntimeError(label + ': Peak crew binding block missing')
    text = text[:ps] + adapt(BAY[bs:be]) + text[pe:]

    # Look & Feel and Recently Deleted bindings.
    bp = BAY.rfind('      planFilesView:')
    bl = BAY.rfind('      brandColor:', 0, bp)
    pp = text.rfind('      planFilesView:')
    pl = text.rfind('      cornerOpts:', 0, pp)
    if min(bp, bl, pp, pl) < 0:
        raise RuntimeError(label + ': Look & Feel binding block missing')
    look = adapt(BAY[bl:bp]).replace('Modern — Jakarta / Barlow', 'Peak — Jakarta / Barlow')
    text = text[:pl] + look + text[pp:]

    # Methods + missing helper dependencies.
    existing = set(method_map(text))
    selected = set(ROOTS)
    queue = list(ROOTS)
    while queue:
        name = queue.pop()
        source = BAY_METHODS.get(name, '')
        for ref in re.findall(r'this\.([A-Za-z_$][\w$]*)\s*\(', source):
            if ref in BAY_METHODS and ref not in selected and ref not in existing:
                selected.add(ref)
                queue.append(ref)
    for name in sorted(selected):
        if name in ROOTS or name not in existing:
            text = replace_or_insert_method(text, name, BAY_METHODS[name])

    # Sync the saved company + visual settings. Keep Peak's current workspace and schema.
    mm = method_map(text)
    if '__syncKeys' not in mm or '__mergeState' not in mm:
        raise RuntimeError(label + ': sync methods missing')
    a, b, body = mm['__syncKeys']
    close = body.rfind(']')
    if close < 0:
        raise RuntimeError(label + ': sync key list missing')
    for key in ['co', 'brandColor', 'docColor', 'docColorSync']:
        if "'" + key + "'" not in body:
            body = body[:close] + ", '" + key + "'" + body[close:]
            close = body.rfind(']')
    text = text[:a] + body + text[b:]

    mm = method_map(text)
    a, b, body = mm['__mergeState']
    arr = re.search(r"\['quotes'.*?'clockEvents'\]\.forEach", body, re.S)
    if arr and "'crewTasks'" not in arr.group(0):
        old_arr = arr.group(0)
        new_arr = old_arr.replace("'clockEvents'", "'clockEvents', 'crewTasks', 'leaveReqs', 'crewNotes', 'roosters', 'contacts', 'recycle'")
        body = body[:arr.start()] + new_arr + body[arr.end():]
    if 'remote.co && typeof remote.co' not in body:
        pos = body.rfind('return out;')
        if pos < 0:
            raise RuntimeError(label + ': merge return missing')
        merge_extra = "['pkCorner','pkType','brandColor','docColor','docColorSync'].forEach(function (k) { if (remote[k] !== undefined) out[k] = remote[k]; }); if (remote.co && typeof remote.co === 'object') { var lc = s.co || {}, rc = remote.co || {}; out.co = ((+lc._ts || 0) > (+rc._ts || 0)) ? Object.assign({}, rc, lc) : Object.assign({}, lc, rc); out.coDraft = Object.assign({}, out.co); } "
        body = body[:pos] + merge_extra + body[pos:]
    text = text[:a] + body + text[b:]

    required = [
        'Company details &amp; document template', 'Crew &amp; employees', 'Integrations', 'Look &amp; feel', 'Recently deleted',
        'Connect Google Calendar', 'Google / work email', 'Tender H&amp;S policy', 'Save company details',
        'companyLogoUpload', 'hsPolicyUpload', 'crewPhotoUpload', 'gcalConnect', 'setBrandColor', 'coDraft:',
        "ws: 'peak-hb'", 'PEAK PAINTING & DECORATING LTD', 'Peak Painting HB SOR 2026', 'Interior', 'Exterior',
    ]
    for token in required:
        if token not in text:
            raise RuntimeError(label + ': missing ' + token)
    if "ws: 'baywide-dingos-os'" in text:
        raise RuntimeError(label + ': Baywide workspace leak')
    _, _, panel = settings_block(text, True)
    for bad in ['Baywide Dingos', 'Baywide OS', "Baywide's"]:
        if bad in panel:
            raise RuntimeError(label + ': Baywide branding remains in Settings: ' + bad)
    return text


def main():
    targets = ['index.html'] + (['preview/index.html'] if Path('preview/index.html').exists() else [])
    for name in targets:
        p = Path(name)
        old = p.read_text(errors='ignore')
        new = patch_one(old, name)
        p.write_text(new)
        print(name, len(old), '->', len(new))


if __name__ == '__main__':
    main()
