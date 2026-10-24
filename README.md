# Software Factory

The workflow that turns a change into a committed result with proof. One directory, shared by
all your project repositories.

The factory is prose and templates, not a service. Any model and any harness can run it.

## Files

| File | Purpose |
| --- | --- |
| `FACTORY.md` | The workflow. Four stages: isolate, build, prove, ship. Each stage gives one artifact and has one exit condition. |
| `templates/PROOF.md` | The proof block. The fields, the rules for each field, and the short form. |
| `templates/EXAMPLES.md` | Three real proof blocks from this project set, with the gaps named. |
| `tools/factory-worktree.sh` | The isolate stage. `new`, `scan`, `list`, `remove`. |
| `tools/factory.py` | The gate: `check` (secrets, config, privacy, docs, lint, display) and `sync` for the generated gitleaks file. |
| `config/gitleaks.base.toml` | The head of every generated `.gitleaks.toml`: the shared policy. |
| `config/repos.json` | The project list, the shared allowlist paths, and each project's own paths and reason. |
| `factory.config.example` | The configuration template. Copy it to `factory.config`. |

## Configure

The repository holds no absolute location. The paths of this machine live in `factory.config`,
which is gitignored:

```bash
cp factory.config.example factory.config
$EDITOR factory.config        # set PROJECTS_ROOT
```

`PROJECTS_ROOT` is the directory that holds your repositories. Without a config, the scripts use
the parent of this clone.

## Use

1. Read `FACTORY.md` before you start a change.
2. Fill the proof block while you work, not after.
3. Put the block in the pull request body, or in the commit body.

In a Hermes session, load the skill:

```
skill_view(name='software-factory')
```

The skill points at this directory. This directory is the only copy of the text.

## Use the gate in a project CI

The repository has a composite action. A project workflow uses it in two steps:

```yaml
  factory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # full history, so the secret stage sees it all
      - uses: <owner>/software-factory/.github/actions/check@main
        with:
          repo: <the name in config/repos.json>
```

`uses:` accepts no expressions, so the calling workflow must name the owner literally. That is the
one place the account name appears, and it is the same fact as the repository URL. This README uses
a placeholder.

**Visibility rule.** A workflow can use this action only from a repository with the same or stricter
visibility. A **private** project can call it (tested: GBOGH). A **public** project cannot: GitHub
answers `Unable to resolve action`. Six of the seven projects are public, so they need one of these:

- a vendored copy of `tools/factory.py` and `config/`, synced by `sync --write` and checked by the
  config stage, or
- a fine-grained token in each public repo, used with `actions/checkout` of this repository.

The gate itself needs no token for the private case: GitHub passes a scoped token to the runner for
one hour, and this repository grants access to repositories owned by the same user.

## Why it exists

The eight projects had seven copies of `.gitleaks.toml` and all seven had drifted. Lesson 27 in
`ApolloMatrix/docs/lessons/LESSONS_LEARNT.md` is titled "CI that has never run is not evidence".
The same file records that the privacy gate passed when run by hand and had never run in anger.

The knowledge was never the problem. The projects carry 500 to 800 lines of lessons each. The
missing part was a written workflow and one standard artifact for proof.

## Status

| Step | Work | State |
| --- | --- | --- |
| 1 | The four-stage workflow | done |
| 2 | The proof template and examples | done |
| 3 | Worktree lanes, with the two-part secret scan | done |
| 4 | `factory check`: secrets, config drift, privacy, docs, lint | done, local only |
| 5 | A queue for the chores | blocked on 3 and 4 |

## Decisions

- **One source of truth.** The text lives here. The Hermes skill only points at it.
- **No unified project template.** nRF52, ESP32-S3, ESPHome, Connect IQ, Android and Python
  differ too much. A template for all of them is mostly conditionals.
- **No review-bot merge gate.** A review agent may comment. A human merges firmware.
- **The hardware stays the gate.** A green pipeline is not a panel check.
- **Build directories are never shared.** A shared build directory breaks under two concurrent
  builds. The package and toolchain cache is global already.
- **A credential file in a worktree is a warning, not a stop.** A commit that contains one stops
  the line.
- **The generated gitleaks file has one allowlist table.** A second `[allowlist]` table would
  override the first and drop the shared entries without a warning.
- **The gate runs locally, not in CI.** GitHub cannot call a script that lives outside the
  repository. Wiring CI needs the factory published, or a vendored copy in each repo.

## Plan

The full plan, with the evidence survey and the open questions, is at
`../.hermes/plans/2026-10-24_125929-software-factory.md`.
