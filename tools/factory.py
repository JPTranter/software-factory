#!/usr/bin/env python3
"""The factory check: one gate that every project runs.

Usage
-----
    python tools/factory.py check [repo ...]        # gate the given projects (default: all)
    python tools/factory.py sync [--write] [repo ...]  # regenerate .gitleaks.toml

Stages (a failed stage exits non-zero):

    secrets   gitleaks over the committed history, using the project's config
    config    .gitleaks.toml matches the generated file from config/repos.json
    privacy   no absolute home paths or user names in tracked files
    docs      every relative markdown link resolves
    lint      every tracked Python file compiles

The project list and the per-project allowlist extras live in config/repos.json.
The projects root comes from factory.config (see README). No absolute location
is written in this file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTORY = HERE.parent
CONFIG = Path(os.environ.get("FACTORY_CONFIG", FACTORY / "factory.config"))


def read_key(key: str) -> str:
    """Read a key from factory.config. The file is data, never executed."""
    if not CONFIG.is_file():
        return ""
    for line in CONFIG.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith(key) and "=" in line:
            return line.split("=", 1)[1].strip()
    return ""


def projects_root() -> Path:
    # The environment wins: CI points it at a temporary root that holds a link to
    # the calling workspace.
    env = os.environ.get("PROJECTS_ROOT", "").strip()
    if env:
        return Path(env)
    root = read_key("PROJECTS_ROOT")
    if root:
        return Path(root)
    # No config: the root is the parent of this clone.
    return FACTORY.parent


def load_config() -> dict:
    data = json.loads((FACTORY / "config" / "repos.json").read_text(encoding="utf-8"))
    return data


def load_repos() -> dict:
    return load_config()["repos"]


def target_repos(names: list[str]) -> list[str]:
    repos = load_repos()
    if names:
        unknown = [n for n in names if n not in repos]
        if unknown:
            sys.exit(f"factory: unknown project(s): {', '.join(unknown)}")
        return names
    root = projects_root()
    return [n for n in repos if (root / n / ".git").is_dir()]


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return out.stdout


def tracked_files(repo: Path) -> list[str]:
    return [line for line in git(repo, "ls-files").splitlines() if line]


def norm(text: str) -> str:
    """Compare text across line endings and trailing spaces."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


# ---------------------------------------------------------------- gitleaks file


def render_gitleaks(repo_name: str, note: str, extra: list[str], shared: list[str]) -> str:
    """One file, one allowlist table: shared paths first, then the project's own.

    A second `[allowlist]` table would override the first and drop the shared
    entries without a warning, so this function never writes two.
    """
    base = norm((FACTORY / "config" / "gitleaks.base.toml").read_text(encoding="utf-8"))
    paths = list(shared) + [e for e in extra if e not in shared]
    lines = [
        "# GENERATED FILE - do not edit.",
        "# Written by: software-factory/tools/factory.py sync",
        "# Head:       software-factory/config/gitleaks.base.toml",
        "# Paths:      software-factory/config/repos.json, entry " + json.dumps(repo_name),
        "#",
        "# " + note.replace("\n", "\n# "),
        "",
        base,
        "",
        "[allowlist]",
        "paths = [",
    ]
    lines.extend(f"    '''{entry}'''," for entry in paths)
    lines.append("]")
    return "\n".join(lines) + "\n"


def stage_config(repo: Path, name: str, extras: dict) -> tuple[bool, str]:
    entry = extras.get(name)
    if entry is None:
        return True, "no entry in repos.json - skipped"
    shared = load_config()["shared"]
    path = repo / ".gitleaks.toml"
    want = norm(render_gitleaks(name, entry["note"], entry.get("extra", []), shared))
    if not path.is_file():
        return False, "missing .gitleaks.toml - run: factory.py sync --write"
    if norm(path.read_text(encoding="utf-8", errors="replace")) != want:
        return False, "does not match the generated file - run: sync --write"
    return True, "matches the generated file"


# -------------------------------------------------------------------- gitleaks


def stage_secrets(repo: Path) -> tuple[bool, str]:
    exe = shutil.which("gitleaks")
    if not exe:
        return False, "gitleaks not on PATH"
    args = [exe, "git", str(repo), "--no-banner", "--redact", "--exit-code", "1"]
    cfg = repo / ".gitleaks.toml"
    if cfg.is_file():
        args += ["--config", str(cfg)]
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode == 0:
        return True, "no leaks in history"
    return False, f"findings (exit {out.returncode}) - see: gitleaks git {repo} --redact -v"


# --------------------------------------------------------------------- privacy


# A name in a home path that is a placeholder, not a person.
PLACEHOLDERS = {
    "<user>", "<name>", "<username>", "<you>", "%username%", "$username", "$user",
    "your-name", "youruser", "you", "user", "username", "name", "owner", "me", "someone",
    # An ellipsis means "some name goes here". The lessons files use it.
    "...", "\u2026", "x", "xxx",
}
DRIVE_USERS = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s'\"`)\]]+)")
POSIX_USERS = re.compile(
    r"(?:/c/|/mnt/c/)?/Users/([^/\s'\"`)\]]+)|/home/([^/\s'\"`)\]]+)"
)


NAME_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


def _home_names(line: str) -> set[str]:
    """Names after /Users/ or /home/. A regex literal in a checker is not a name."""
    names = {m.group(1) for m in DRIVE_USERS.finditer(line)}
    names |= {(m.group(1) or m.group(2)) for m in POSIX_USERS.finditer(line)}
    return {n for n in names if n and NAME_SHAPE.match(n)}


def stage_privacy(repo: Path) -> tuple[bool, str]:
    """A tracked file must not carry a person's home path.

    A placeholder is allowed: `C:/Users/<user>/...`, `$HOME`, `%USERNAME%`.
    A real name is not. Text inside backticks counts: a path in a code example is
    still a path a reader copies.
    """
    skip = (".pio", "build", "output", ".venv", "node_modules", "third_party", "docs/images")
    binary = (".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".pdf", ".woff", ".ttf")
    bad: list[str] = []
    for rel in tracked_files(repo):
        if any(part in rel for part in skip) or rel.endswith(binary):
            continue
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "factory:ignore" in line:
                continue
            names = _home_names(line)
            real = sorted(n for n in names if n.lower() not in PLACEHOLDERS)
            if real:
                bad.append(f"{rel}:{lineno} ({', '.join(real)})")
                break
    if bad:
        return False, f"{len(bad)} file(s): " + ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else "")
    return True, "no person's home path in tracked files"


# ------------------------------------------------------------------------ docs


def stage_docs(repo: Path) -> tuple[bool, str]:
    link = re.compile(r"\]\(([^)\s]+)")
    missing: list[str] = []
    checked = 0
    for rel in tracked_files(repo):
        if not rel.lower().endswith(".md"):
            continue
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fenced = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced or "factory:ignore" in line:
                continue
            # Inline code shows syntax, not a link. `![alt](path)` is documentation.
            bare = re.sub(r"`[^`]*`", "", line)
            for target in link.findall(bare):
                if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                    continue
                if target.startswith("file://"):
                    checked += 1
                    missing.append(f"{rel} -> absolute file link")
                    continue
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                checked += 1
                if not (path.parent / clean).exists() and not (repo / clean).exists():
                    missing.append(f"{rel} -> {clean}")
    if missing:
        return False, f"{len(missing)} broken link(s): " + "; ".join(missing[:4])
    return True, f"{checked} relative link(s) resolve"


# ------------------------------------------------------------------------ lint


def stage_lint(repo: Path) -> tuple[bool, str]:
    files = [f for f in tracked_files(repo) if f.endswith(".py")]
    if not files:
        return True, "no Python files"
    exe = sys.executable
    out = subprocess.run(
        [exe, "-m", "py_compile", *files], capture_output=True, text=True, cwd=str(repo)
    )
    if out.returncode == 0:
        return True, f"{len(files)} file(s) compile"
    return False, " ".join(out.stderr.strip().splitlines()[:3]) or f"exit {out.returncode}"


# --------------------------------------------------------------------- display


def _srgb_lum(rgb: tuple[int, int, int]) -> float:
    def channel(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb[:3]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _srgb_lum(a), _srgb_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def stage_display(repo: Path, name: str, extras: dict) -> tuple[bool, str]:
    """The measurable floor of a presentation change.

    Geometry, palette size and ink-to-background contrast are numbers, so they are
    gated. Marginal ink, coverage and the aesthetic judgement are reported for the
    human review, which no script can replace.
    """
    spec = (extras.get(name) or {}).get("display")
    if not spec:
        return True, "no display spec in repos.json - skipped"
    try:
        from PIL import Image
    except ImportError:
        return True, "pillow not installed - skipped"

    pattern = spec.get("renders", "")
    exclude = set(spec.get("exclude", []))
    width, height = int(spec["width"]), int(spec["height"])
    max_colours = int(spec.get("max_colours", 4))
    min_contrast = float(spec.get("min_contrast", 4.5))

    files = [f for f in sorted(repo.glob(pattern)) if f.name not in exclude]
    if not files:
        return False, f"no panel render matches {pattern}"

    faults: list[str] = []
    notes: list[str] = []
    for f in files:
        rel = f.relative_to(repo).as_posix()
        try:
            im = Image.open(f).convert("RGBA")
        except OSError as exc:
            faults.append(f"{rel}: unreadable ({exc})")
            continue
        size = im.size
        if size not in ((width, height), (height, width)):
            faults.append(f"{rel}: {size[0]}x{size[1]}, panel is {width}x{height}")
            continue
        colours = im.getcolors(maxcolors=1 << 22) or []
        opaque = [(n, c) for n, c in colours if c[3] > 10]
        if not opaque:
            faults.append(f"{rel}: fully transparent")
            continue
        opaque.sort(reverse=True)
        bg = opaque[0][1][:3]
        distinct = len(opaque)
        if distinct > max_colours:
            faults.append(f"{rel}: {distinct} colours, panel allows {max_colours}")
        best = max((_contrast(c[:3], bg) for _, c in opaque[1:]), default=0.0)
        if best < min_contrast:
            faults.append(f"{rel}: best ink contrast {best:.2f}:1, need {min_contrast:g}:1")

        # Reports, not gates: the eye decides on these.
        w, h = size
        edge = 0
        for x in range(w):
            for y in (0, h - 1):
                if im.getpixel((x, y))[:3] != bg:
                    edge += 1
        for y in range(h):
            for x in (0, w - 1):
                if im.getpixel((x, y))[:3] != bg:
                    edge += 1
        ink = sum(n for n, c in opaque[1:])
        total = sum(n for n, _ in opaque)
        notes.append(f"{rel.split('/')[-1]} {best:.1f}:1 ink {100 * ink / total:.0f}%")
        if edge:
            notes.append(f"{rel.split('/')[-1]} edge_ink {edge}px")

    head = f"{len(files)} render(s), panel {width}x{height}, palette {max_colours}"
    if faults:
        return False, head + "; " + "; ".join(faults[:4])
    return True, head + " | " + ", ".join(notes[:6])

STAGES = ("secrets", "config", "privacy", "docs", "lint", "display")


def run_stage(stage: str, repo: Path, name: str, extras: dict) -> tuple[bool, str]:
    if stage == "secrets":
        return stage_secrets(repo)
    if stage == "config":
        return stage_config(repo, name, extras)
    if stage == "privacy":
        return stage_privacy(repo)
    if stage == "docs":
        return stage_docs(repo)
    if stage == "display":
        return stage_display(repo, name, extras)
    return stage_lint(repo)


def cmd_check(names: list[str]) -> int:
    root = projects_root()
    repos = target_repos(names)
    extras = load_repos()
    if not repos:
        sys.exit(f"factory: no project repositories under {root}")
    failed = 0
    for name in repos:
        repo = root / name
        print(f"\n=== {name}")
        for stage in STAGES:
            ok, detail = run_stage(stage, repo, name, extras)
            print(f"  {'PASS' if ok else 'FAIL'}  {stage:<8} {detail}")
            if not ok:
                failed += 1
    print(f"\n{len(repos)} project(s), {failed} failed stage(s)")
    return 1 if failed else 0


def cmd_selfcheck() -> int:
    """Run the gate over this repository. No config stage: it generates the configs."""
    failed = 0
    print(f"=== {FACTORY.name}")
    for stage in ("secrets", "privacy", "docs", "lint"):
        ok, detail = run_stage(stage, FACTORY, FACTORY.name, {})
        print(f"  {'PASS' if ok else 'FAIL'}  {stage:<8} {detail}")
        if not ok:
            failed += 1
    print(f"\n{failed} failed stage(s)")
    return 1 if failed else 0


def cmd_sync(names: list[str], write: bool) -> int:
    root = projects_root()
    data = load_repos()
    shared = json.loads((FACTORY / "config" / "repos.json").read_text(encoding="utf-8"))["shared"]
    for name in target_repos(names):
        entry = data.get(name)
        if not entry:
            print(f"{name}: no entry in repos.json - skipped")
            continue
        want = render_gitleaks(name, entry["note"], entry.get("extra", []), shared)
        path = root / name / ".gitleaks.toml"
        have = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        if norm(have) == norm(want):
            print(f"{name}: unchanged")
            continue
        print(f"{name}: {'wrote' if write else 'would write'} .gitleaks.toml")
        if write:
            path.write_text(want, encoding="utf-8", newline="\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="factory", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="run the gate")
    chk.add_argument("repos", nargs="*")
    syn = sub.add_parser("sync", help="regenerate the gitleaks config")
    syn.add_argument("repos", nargs="*")
    syn.add_argument("--write", action="store_true", help="write the files (dry run without it)")
    sub.add_parser("selfcheck", help="run the gate over this repository")
    args = ap.parse_args()
    if args.cmd == "selfcheck":
        return cmd_selfcheck()
    if args.cmd == "check":
        return cmd_check(args.repos)
    return cmd_sync(args.repos, args.write)


if __name__ == "__main__":
    sys.exit(main())
