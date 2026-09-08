#!/usr/bin/env python3
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

PEAK_MARKERS = [
    "Peak Paint",
    "PEAK PAINT",
    "peak-paint",
    "Painting & Decorating",
    "Painting &amp; Decorating",
    "rateExteriorWalls",
    "rateCeilings",
    "rateDoors",
    "painter",
    "painting",
    "paintwork",
    "primer",
]

BAYWIDE_BRAND_MARKERS = [
    "Baywide Dingos",
    "BAYWIDE DINGOS",
    "baywide-dingos",
]

GENERIC_PARITY_MARKERS = [
    "Google Calendar",
    "Recently deleted",
    "Progress Claims",
    "Tax Invoices",
    "Planned Hours",
    "Actual Hours",
    'data-settings-tab="company"',
    'data-settings-tab="crew"',
    'data-settings-tab="integrations"',
    'data-settings-tab="look"',
    'data-settings-tab="deleted"',
]


def run(cmd, *, cwd=None, check=True, capture=False):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
    )


def prettier(src: pathlib.Path, dst: pathlib.Path):
    with src.open("r", encoding="utf-8") as inp, dst.open("w", encoding="utf-8") as out:
        proc = subprocess.run(
            ["npx", "--yes", "prettier@3.6.2", "--parser", "html"],
            stdin=inp,
            stdout=out,
            stderr=subprocess.PIPE,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"Prettier failed for {src}: {proc.stderr}")


def contains_any(text, markers):
    low = text.lower()
    return any(m.lower() in low for m in markers)


def resolve_diff3(text: str):
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    conflicts = 0
    current_kept = 0
    latest_kept = 0

    while i < len(lines):
        if not lines[i].startswith("<<<<<<<"):
            out.append(lines[i])
            i += 1
            continue

        conflicts += 1
        i += 1
        cur = []
        while i < len(lines) and not lines[i].startswith("|||||||"):
            cur.append(lines[i]); i += 1
        if i >= len(lines):
            raise RuntimeError("Malformed diff3 conflict: missing base marker")
        i += 1
        base = []
        while i < len(lines) and not lines[i].startswith("======="):
            base.append(lines[i]); i += 1
        if i >= len(lines):
            raise RuntimeError("Malformed diff3 conflict: missing separator")
        i += 1
        latest = []
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            latest.append(lines[i]); i += 1
        if i >= len(lines):
            raise RuntimeError("Malformed diff3 conflict: missing end marker")
        i += 1

        cur_s = "".join(cur)
        base_s = "".join(base)
        latest_s = "".join(latest)

        # Preserve Peak-specific branding/trade/rates/H&S content whenever a
        # Baywide generic update collides with it. Otherwise Baywide latest wins.
        cur_is_peak = contains_any(cur_s, PEAK_MARKERS)
        latest_is_bay_brand = contains_any(latest_s, BAYWIDE_BRAND_MARKERS)
        base_is_bay_brand = contains_any(base_s, BAYWIDE_BRAND_MARKERS)

        if cur_is_peak or latest_is_bay_brand or base_is_bay_brand:
            out.append(cur_s)
            current_kept += 1
        else:
            out.append(latest_s)
            latest_kept += 1

    return "".join(out), conflicts, current_kept, latest_kept


def require_markers(final_text: str, latest_text: str, peak_text: str):
    missing = []

    # Preserve Peak-specific markers that existed before the sync.
    for marker in PEAK_MARKERS:
        if marker.lower() in peak_text.lower() and marker.lower() not in final_text.lower():
            missing.append(f"Peak marker lost: {marker}")

    # Carry the known shared Baywide functionality whenever present upstream.
    for marker in GENERIC_PARITY_MARKERS:
        if marker.lower() in latest_text.lower() and marker.lower() not in final_text.lower():
            missing.append(f"Baywide parity marker missing: {marker}")

    # Never leak Baywide company branding into Peak.
    for marker in BAYWIDE_BRAND_MARKERS:
        if marker.lower() in final_text.lower():
            missing.append(f"Baywide branding leaked into Peak: {marker}")

    if "<<<<<<<" in final_text or "|||||||" in final_text or ">>>>>>>" in final_text:
        missing.append("Unresolved merge conflict markers remain")

    if missing:
        raise RuntimeError("Parity QA failed:\n - " + "\n - ".join(missing))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--peak", required=True)
    ap.add_argument("--baywide-repo", required=True)
    ap.add_argument("--baywide-base", required=True)
    ap.add_argument("--preview")
    args = ap.parse_args()

    peak_path = pathlib.Path(args.peak).resolve()
    repo = pathlib.Path(args.baywide_repo).resolve()
    preview_path = pathlib.Path(args.preview).resolve() if args.preview else None

    if not peak_path.exists():
        raise SystemExit(f"Peak source not found: {peak_path}")

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        peak_raw = td / "peak.raw.html"
        base_raw = td / "base.raw.html"
        latest_raw = td / "latest.raw.html"
        peak_fmt = td / "peak.pretty.html"
        base_fmt = td / "base.pretty.html"
        latest_fmt = td / "latest.pretty.html"
        merged_fmt = td / "merged.pretty.html"
        final_fmt = td / "final.pretty.html"

        shutil.copy2(peak_path, peak_raw)
        with base_raw.open("w", encoding="utf-8") as f:
            proc = subprocess.run(
                ["git", "show", f"{args.baywide_base}:index.html"],
                cwd=repo,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
            )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)
        shutil.copy2(repo / "index.html", latest_raw)

        print("Formatting three merge inputs...", flush=True)
        prettier(peak_raw, peak_fmt)
        prettier(base_raw, base_fmt)
        prettier(latest_raw, latest_fmt)

        proc = subprocess.run(
            ["git", "merge-file", "-p", "--diff3", str(peak_fmt), str(base_fmt), str(latest_fmt)],
            text=True,
            capture_output=True,
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"git merge-file failed: {proc.stderr}")

        resolved, conflicts, current_kept, latest_kept = resolve_diff3(proc.stdout)
        merged_fmt.write_text(resolved, encoding="utf-8")
        print(
            f"Three-way merge: {conflicts} conflicts; "
            f"kept Peak side {current_kept}; kept Baywide latest side {latest_kept}",
            flush=True,
        )

        prettier(merged_fmt, final_fmt)
        final_text = final_fmt.read_text(encoding="utf-8")
        latest_text = latest_raw.read_text(encoding="utf-8")
        peak_text = peak_raw.read_text(encoding="utf-8")
        require_markers(final_text, latest_text, peak_text)

        peak_path.write_text(final_text, encoding="utf-8")
        if preview_path:
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(final_text, encoding="utf-8")

        print(f"Final Peak index size: {peak_path.stat().st_size:,} bytes", flush=True)
        print("Full Baywide parity QA passed.", flush=True)


if __name__ == "__main__":
    main()
