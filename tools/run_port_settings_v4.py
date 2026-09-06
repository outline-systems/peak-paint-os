from pathlib import Path

src_path = Path('tools/port_baywide_settings_v2.py')
src = src_path.read_text()

old_pat = "pat = re.compile(r'(?:^|\\n|\\\\n)([ \\t]{2})([A-Za-z_$][\\w$]*)\\s*\\(')"
new_pat = "pat = re.compile(r'(?:^|\\n|\\\\n)([ \\t]{2,})([A-Za-z_$][\\w$]*)\\s*\\(')"
if old_pat not in src:
    raise SystemExit('Expected method parser pattern not found')
src = src.replace(old_pat, new_pat, 1)

old_locals = """    if '__coSavedPolicy' not in text[max(0, cof - 5000):cof]:
        bw_cof = BAY.rfind('const coF = (k) =>')
        va = BAY.rfind('var __coSaved', 0, bw_cof)
        if va < 0:
            raise RuntimeError('Baywide company render locals missing')
        text = text[:cof] + adapt(BAY[va:bw_cof]) + text[cof:]
"""
new_locals = """    if '__coSavedPolicy' not in text[max(0, cof - 5000):cof]:
        locals_src = (
            "var __coSaved = S.co || {};" + sep +
            "      var __coEdit = S.coDraft || __coSaved;" + sep +
            "      var __coSavedPolicy = (__coSaved && __coSaved.hsPolicy) || null;" + sep +
            "      var __coEditPolicy = (__coEdit && __coEdit.hsPolicy) || null;" + sep +
            "      var hsPolicyPages = (__coSavedPolicy && Array.isArray(__coSavedPolicy.pages)) ? __coSavedPolicy.pages : [];" + sep +
            "      "
        )
        text = text[:cof] + locals_src + text[cof:]
"""
if old_locals not in src:
    raise SystemExit('Expected company-locals patch block not found')
src = src.replace(old_locals, new_locals, 1)

namespace = {'__name__': '__main__', '__file__': str(src_path)}
exec(compile(src, str(src_path), 'exec'), namespace)
