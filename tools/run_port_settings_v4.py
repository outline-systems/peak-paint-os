from pathlib import Path

src_path = Path('tools/port_baywide_settings_v2.py')
src = src_path.read_text()

# Keep the original exact two-space class-method parser. Broadening this to
# nested indentation causes local functions inside methods to be mistaken for
# class methods and produces truncated/invalid JavaScript.

# Baywide's Settings markup contains trade-specific crew-role labels. Preserve
# the Peak painting equivalents while copying the UI and behavior.
role_anchor = "        ('Baywide Blue', 'Peak Blue'),\n"
role_replacement = role_anchor + "        ('Senior operator', 'Senior painter'),\n        ('Operator', 'Painter'),\n"
if role_anchor not in src:
    raise SystemExit('Expected Settings trade-role adaptation anchor not found')
src = src.replace(role_anchor, role_replacement, 1)

old_anchor = """    if 'render' not in cur:
        raise RuntimeError('render() missing while inserting ' + name)
    a = cur['render'][0]
"""
new_anchor = """    anchor = 'render' if 'render' in cur else ('renderVals' if 'renderVals' in cur else None)
    if not anchor:
        raise RuntimeError('render/renderVals anchor missing while inserting ' + name)
    a = cur[anchor][0]
"""
if old_anchor not in src:
    raise SystemExit('Expected render insertion block not found')
src = src.replace(old_anchor, new_anchor, 1)

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
