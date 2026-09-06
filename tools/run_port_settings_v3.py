from pathlib import Path

src_path = Path('tools/port_baywide_settings_v2.py')
src = src_path.read_text()

old = """    if '__coSavedPolicy' not in text[max(0, cof - 5000):cof]:
        bw_cof = BAY.rfind('const coF = (k) =>')
        va = BAY.rfind('var __coSaved', 0, bw_cof)
        if va < 0:
            raise RuntimeError('Baywide company render locals missing')
        text = text[:cof] + adapt(BAY[va:bw_cof]) + text[cof:]
"""
new = """    if '__coSavedPolicy' not in text[max(0, cof - 5000):cof]:
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

if old not in src:
    raise SystemExit('Expected v2 company-locals patch block not found')

patched = src.replace(old, new, 1)
namespace = {'__name__': '__main__', '__file__': str(src_path)}
exec(compile(patched, str(src_path), 'exec'), namespace)
