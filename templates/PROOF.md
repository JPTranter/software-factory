# The Proof Block

One block for one change. Put it in the pull request body. If the change has no pull request,
put it in the commit body.

The block is not a summary of the diff. It shows that the change works. A person who did not
do the work must be able to judge the change from the block alone.

## Skeleton

```markdown
## Proof

**Change:** <one sentence, active voice>
**Base commit:** <hash>  **Station:** <worktree path | none — docs only>
**Gate run:** `<command>` → `<result>`

### Before

<image path, command output, or numbers>

### After

<image path, command output, or numbers>

### Numbers

| Measure | Before | After | How measured |
| --- | --- | --- | --- |
| <name> | <value> | <value> | <tool, unit, where> |

### Evidence locations

- Ledger: `docs/images/<file>.png` — byte-compared on every gate run
- History: `docs/images/history/<file>.png` — the render a decision was made from
- Gitignored: `<path>` — preview only, never cited as proof

### Not proved

<what this change does not show, and why that is safe>
```

### Display review (presentation changes only)

Fill this in for anything a person will look at. Rules P1 to P7 in `FACTORY.md`.

| Criterion | Evidence | Verdict |
| --- | --- | --- |
| Readability | smallest text <n> px, judged at <distance>, from the <device-font/fallback> build | <pass / change needed> |
| Usability | <n> steps, <n> button presses to reach <goal> | |
| Ease of use | first use: <what happens with no instructions>. Missing or long data: <what happens> | |
| Character | the thing that carries it: <one specific feature> | |

**Numbers:** ink coverage <n>%, contrast <n>:1, refresh <n> s, palette <n> colours.
**Hardware limit stated:** <e.g. 4-colour 296x128, 2 s full refresh, no partial-update ghosting allowed>
**Reviewed by:** <independent reviewer: a separate agent session, or a human>. **Shown only:**
<the approved render, the goal, the hardware limits — not the author's rationale>.
**Approved render:** `<docs/images/history/...png>`

## Rules for each field

**Change.** One sentence. Name the behavior, not the file. Bad: "change wrap.cpp". Good: "The
verse box now uses the footer row, so a long verse keeps whole lines."

**Base commit.** The commit the change starts from. Use `git rev-parse HEAD` before you edit.

**Station.** The worktree path. Write `none — docs only` when the change has no worktree. Give
the reason.

**Gate run.** The exact command and the exact result. Copy the last line. Do not write "tests
pass". Write `python tools/verify_all.py → 6/6 stages PASS`.

**Before and After.** Use the same command and the same input for both. An image, a log excerpt,
or a number. If you did not capture the before state, write `not captured` and say why. Do not
reconstruct it from memory.

**Numbers.** Required when the surface is invisible: current, time, memory, size, passes. Give
the unit and the tool. A number without a measurement method is a claim.

**Evidence locations.** Use the three places in this order of authority:
1. The ledger, `docs/images/` (ChromaWOTD, GBOGH). The gate compares it byte for byte.
2. The history folder, `docs/images/history/`. It holds the renders that a human decided from.
   eClock keeps its approved renders in `docs/screenshots/`.
3. A gitignored `output/` path. Preview work only.

**Not proved.** Name the limit. Example: "Not measured on the panel. The render is from the host
build, so the panel font is not shown. Safe because the change touches the wrap width only."

## Short form

For a one-line fix or a documentation change:

```markdown
## Proof (short)

**Broke:** <the symptom, in one line>
**Changed:** <the line or the section>
**How I know:** <the command, the output, or the observation>
```

The short form is allowed. Silence is not. Write "not applicable" and the reason.

## Prohibited

- A proof block with no artifact.
- A cited image that lives in a gitignored directory.
- A hardware claim with no hardware observation.
- Numbers with no unit or no method.
- "Should work", "likely fixes", "appears correct".
