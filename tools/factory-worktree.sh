#!/usr/bin/env bash
# factory-worktree.sh - the isolate stage of the factory workflow.
#
# One change gets one worktree, branched from the remote default branch. The
# script records the base commit, then scans the worktree.
#
# Usage:
#   tools/factory-worktree.sh new    <repo> <slug> [--base <ref>]
#   tools/factory-worktree.sh scan   <repo> <slug>
#   tools/factory-worktree.sh list   [repo]
#   tools/factory-worktree.sh remove <repo> <slug>
#
# Example:
#   tools/factory-worktree.sh new ChromaWOTD fix-footer-row
#   cd ../_worktrees/ChromaWOTD--fix-footer-row
#
# Worktrees live in $PROJECTS_ROOT/_worktrees/<repo>--<slug>, outside every
# repository. A sidecar file `<repo>--<slug>.meta` holds the base commit for the
# proof block.
#
# The projects root comes from `factory.config`, next to this directory, or from
# the file that FACTORY_CONFIG names. Without a config, the root is the parent of
# this repository. Nothing here contains an absolute location.
#
# The secret scan has two parts:
#   1. BLOCKING - gitleaks over the committed history of the worktree.
#   2. WARNING  - gitignored files that normally carry credentials are listed by
#                  name only. Their contents are never printed.
#
# Build directories are never shared. Sharing one build directory between two
# concurrent builds corrupts it. The PlatformIO package and toolchain cache is
# already global (~/.platformio), so the worktree shares it without any setting.
set -euo pipefail

# Native Windows paths (C:/...) are required: git and gitleaks are native
# programs and do not understand MSYS paths such as /c/...
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -W 2>/dev/null || pwd)"
CONFIG="${FACTORY_CONFIG:-$here/../factory.config}"
DERIVED_ROOT="$(cd "$here/../.." && pwd -W 2>/dev/null || pwd)"

# The config is read as data, never sourced: a CRLF or a stray command in it must
# not run.
read_key() {
  [ -f "$CONFIG" ] || return 0
  sed -n "s/^[[:space:]]*$1[[:space:]]*=//p" "$CONFIG" | tr -d '\r' | sed 's/[[:space:]]*$//' | tail -1
}
PROJECTS="$(read_key PROJECTS_ROOT)"
WORKTREES="$(read_key WORKTREE_ROOT)"
PROJECTS="${PROJECTS:-$DERIVED_ROOT}"
WORKTREES="${WORKTREES:-$PROJECTS/_worktrees}"
PROJECTS="${PROJECTS%/}"; PROJECTS="${PROJECTS%\\}"
WORKTREES="${WORKTREES%/}"; WORKTREES="${WORKTREES%\\}"
[ -d "$PROJECTS" ] || { echo "factory: projects root not found: $PROJECTS" >&2; \
  echo "  set PROJECTS_ROOT in $CONFIG" >&2; exit 1; }

die() { echo "factory: $*" >&2; exit 1; }
note() { echo "  $*"; }

repo_path() {
  local repo="$1"
  [ -d "$PROJECTS/$repo/.git" ] || die "no git repository at $PROJECTS/$repo"
  echo "$PROJECTS/$repo"
}

default_ref() {
  local dir="$1"
  if git -C "$dir" remote >/dev/null 2>&1 && [ -n "$(git -C "$dir" remote)" ]; then
    local head
    head="$(git -C "$dir" symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null || true)"
    if [ -n "$head" ]; then
      echo "${head#refs/remotes/}"
      return
    fi
    # No origin/HEAD: use the branch that is checked out.
    echo "origin/$(git -C "$dir" rev-parse --abbrev-ref HEAD)"
    return
  fi
  echo "$(git -C "$dir" rev-parse --abbrev-ref HEAD)"
}

cmd_new() {
  local repo="$1" slug="$2" base="${3:-}"
  local dir; dir="$(repo_path "$repo")"
  [ -n "$slug" ] || die "a slug is required"

  local path="$WORKTREES/${repo}--${slug}"
  [ -e "$path" ] && die "worktree already exists: $path"

  if [ -z "$base" ]; then
    if git -C "$dir" remote | grep -q .; then
      note "fetching $repo"
      git -C "$dir" fetch --quiet origin || die "fetch failed"
    fi
    base="$(default_ref "$dir")"
  fi

  local commit
  commit="$(git -C "$dir" rev-parse --short "$base" 2>/dev/null)" || die "cannot resolve base ref: $base"

  mkdir -p "$WORKTREES"
  note "creating worktree from $base at $commit"
  git -C "$dir" worktree add -b "factory/$slug" "$path" "$base" >/dev/null || die "worktree add failed"

  {
    echo "repo=$repo"
    echo "slug=$slug"
    echo "path=$path"
    echo "base_ref=$base"
    echo "base_commit=$commit"
    echo "branch=factory/$slug"
    echo "created=$(date +%Y-%m-%dT%H:%M:%S)"
  } > "$WORKTREES/${repo}--${slug}.meta"

  echo "worktree: $path"
  echo "base commit: $commit  (put this in the proof block)"
  echo "branch: factory/$slug"
  echo
  cmd_scan "$repo" "$slug"
}

cmd_scan() {
  local repo="$1" slug="$2"
  local path="$WORKTREES/${repo}--${slug}"
  [ -d "$path" ] || die "no worktree at $path"
  echo "== scan: $repo--$slug =="

  # 1. Blocking: secrets in committed history.
  local cfg="$path/.gitleaks.toml"
  local args=(git "$path" --no-banner --redact --exit-code 1)
  [ -f "$cfg" ] && args+=(--config "$cfg")
  local rc=0
  if gitleaks "${args[@]}" >/dev/null 2>&1; then
    echo "  history scan: clean"
  else
    rc=$?
    echo "  history scan: FINDINGS or error (exit $rc) - the line stops here" >&2
    echo "  run this to see them, redacted:" >&2
    echo "    gitleaks git \"$path\" --redact -v" >&2
    return $rc
  fi

  # 2. Warning only: ignored files that usually carry credentials. Names only.
  local pattern='(^|/)(secrets\.h|secrets\.yaml|secrets\.yml|\.env|\.env\.[a-z]+|[^/]*\.(pem|p12|pfx|key))$'
  local found
  found="$(cd "$path" && { git ls-files --others --ignored --exclude-standard; git ls-files --others --exclude-standard; } 2>/dev/null | sort -u | grep -Ei "$pattern" || true)"
  if [ -n "$found" ]; then
    echo "  warning: credential-bearing files are present and are NOT committed:"
    echo "$found" | sed 's/^/    /'
    echo "    Do not print their contents. Use: git ls-files ':(glob)src/*.h'"
  else
    echo "  ignored-file scan: no credential files"
  fi
  echo "  (warning only - this does not stop the line)"
}

cmd_list() {
  local filter="${1:-}"
  [ -d "$WORKTREES" ] || { echo "no worktrees"; return; }
  local f
  for f in "$WORKTREES"/*.meta; do
    [ -e "$f" ] || continue
    local repo slug base path
    repo="$(sed -n 's/^repo=//p' "$f")"
    slug="$(sed -n 's/^slug=//p' "$f")"
    base="$(sed -n 's/^base_commit=//p' "$f")"
    path="$(sed -n 's/^path=//p' "$f")"
    [ -z "$filter" ] || [ "$repo" = "$filter" ] || continue
    printf '%-14s %-28s %-8s %s\n' "$repo" "$slug" "$base" "$( [ -d "$path" ] && echo present || echo MISSING )"
  done
}

cmd_remove() {
  local repo="$1" slug="$2"
  local dir; dir="$(repo_path "$repo")"
  local path="$WORKTREES/${repo}--${slug}"
  git -C "$dir" worktree remove --force "$path" 2>/dev/null || rm -rf "$path"
  git -C "$dir" worktree prune
  # The branch belongs to the worktree. Delete it, unless it has commits that
  # main does not have. Then the user decides.
  if git -C "$dir" merge-base --is-ancestor "factory/$slug" HEAD 2>/dev/null; then
    git -C "$dir" branch -D "factory/$slug" >/dev/null 2>&1 || true
  else
    echo "kept branch factory/$slug - it has commits that HEAD does not have" >&2
  fi
  rm -f "$WORKTREES/${repo}--${slug}.meta"
  echo "removed $path"
}

main() {
  local cmd="${1:-}"; shift || true
  case "$cmd" in
    new)    [ $# -ge 2 ] || die "usage: new <repo> <slug> [--base <ref>]"
            local repo="$1" slug="$2"; shift 2
            local base=""
            if [ "${1:-}" = "--base" ]; then base="${2:-}"; fi
            cmd_new "$repo" "$slug" "$base" ;;
    scan)   [ $# -ge 2 ] || die "usage: scan <repo> <slug>"; cmd_scan "$1" "$2" ;;
    list)   cmd_list "${1:-}" ;;
    remove) [ $# -ge 2 ] || die "usage: remove <repo> <slug>"; cmd_remove "$1" "$2" ;;
    *)      sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1 ;;
  esac
}

main "$@"
