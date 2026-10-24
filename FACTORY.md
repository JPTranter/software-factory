# The Factory Workflow

A factory makes one change at a time, at a station, and it keeps the proof. This file is the
whole workflow. It is prose on purpose: any model and any harness can run it.

Four stages: **isolate, build, prove, ship**. Each stage gives one artifact. No stage starts
before the exit condition of the stage before it is true.

## Terms

| Term | Meaning |
| --- | --- |
| change | One feature, one fix, one document update. It has one commit series. |
| station | The private place where the change is made. A git worktree. |
| artifact | The thing the stage produces. A path, a diff, a table, an image. |
| proof bundle | The stage 3 artifact. Before state, after state, and the numbers. |
| gate | A check that must pass. A failed gate stops the line. |

## Stage 1 — Isolate

**Do:**
1. Run one command. It fetches, branches from the remote default branch, records the base
   commit, and scans:

   ```
   software-factory/tools/factory-worktree.sh new <repo> <slug>
   ```

2. Work in `$PROJECTS_ROOT/_worktrees/<repo>--<slug>/`. One change, one worktree. The root
   comes from `factory.config`.
3. Do not share a build directory between two worktrees. Two concurrent builds corrupt it.
   The PlatformIO package and toolchain cache is global already, so the worktree shares it
   with no setting.
4. AMOLED241 keeps its own `tools/pio.sh` and core directory. Use it inside the worktree.

**Artifact:** the worktree path and the base commit hash. The script prints both.

**The scan has two parts:**
- Committed history: blocking. A finding stops the line.
- Gitignored files that carry credentials: warning only, names printed, contents never printed.
  A worktree that needs `secrets.h` is normal. A commit that contains it is not.

**Exit condition:** the base commit is recorded, the history scan is clean, and each
credential-file warning is understood.

**Skip rule:** a documentation-only change needs no worktree. Write why in the proof block.

## Stage 2 — Build

**Do:**
1. Make the smallest change that reaches the goal.
2. Keep the code readable for the next person and the next agent. Name the layer. Keep the
   hardware quirks in one place.
3. Use the existing skills for this domain. Do not invent a second procedure.
4. If the board contradicts a document, stop. Write down what the board did.

**Artifact:** the diff and the commit message. Use a conventional commit type.

**Exit condition:** the change builds with no new warnings, and the local harness passes.

## Stage 3 — Prove

**Do:**
1. Capture the before state. Capture it before you change the code.
2. Capture the after state with the same command and the same input.
3. When the surface is invisible, give numbers. Current, milliseconds, bytes, passes.
4. Put each image in the correct place:
   - `docs/images/` is the regression ledger. It is byte-compared on every gate run.
   - `docs/images/history/` holds the render a decision was made from.
   - `output/` is gitignored preview work. Never cite it as proof.
5. Fill the proof block. Use `templates/PROOF.md`.

**Artifact:** the proof block, with the images and the numbers.

**Exit condition:** a person who did not do the work can see the difference without reading
the diff. If the change touches hardware, the observation comes from the board.

## Presentation rules

A display is a product, not an output. These rules apply to any change a person will look at:
a face, a screen, a page, an indicator, an animation.

**P1 — Judge it on the panel.** The render must be the panel's own geometry, 1:1. A scaled or
cropped mock is not evidence. The gate enforces this: a render that is not 296x128 on a 296x128
panel fails.

**P2 — The measurable floor is a gate, not an opinion.** Three numbers must hold, and one is
reported:

| Check | Rule |
| --- | --- |
| Geometry | exact panel pixels, either orientation |
| Palette | no more colours than the panel can show (1-bit: 2, BWRY: 4) |
| Contrast | the best ink against the background is at least 4.5:1 |
| Ink coverage | reported, because it drives refresh time, ghosting and power |

`factory check` runs the first three as the `display` stage. Coverage, edge ink and the aesthetic
judgement go in the proof block for a human.

**P3 — State the hardware limit, then design inside it.** Write the limit down before you judge the
design: refresh time in seconds, ghosting from a partial update, 1-bit or 4-colour, no animation,
viewing distance, sunlight, burn-in, viewing angle. A design that is beautiful and unreadable at
the real distance has failed.

**P4 — Four criteria, judged by independent fresh eyes.** The reviewer must not be the agent or the
person who built the change. Use a separate agent session with no knowledge of the work, or a
human. Give the reviewer the approved render, the stated goal and the hardware limits — not the
author's reasoning, the draft iterations, or the defence. Independence is the point: a reviewer who
has followed the build will approve the build.

Each criterion needs one line of evidence, not a verdict alone:

1. **Readability** — the smallest text's height in pixels, and why that is enough at the intended
   distance. For type, judge the device-font build, not the fallback build.
2. **Usability** — can the person reach the information or the control in the fewest steps the
   hardware allows? Count the steps and the button presses.
3. **Ease of use** — what happens on the first use, with no instructions, and what happens when the
   data is missing, stale, absurd, or long.
4. **Character** — does it look deliberate and alive on this panel? Name the one thing that carries
   the character. "Fine" is not an answer.

**P5 — Report what the review measured.** Numbers in the proof block: smallest text px, ink
coverage, refresh cost, contrast. An approved render with no numbers is a taste claim.

**P6 — Keep the record.** The approved render goes to the history folder. The decision, and its
reason, go to the project's display history (`UI_HISTORY.md` or equivalent) and to
`LESSONS_LEARNT.md` when it cost something to learn.

**P7 — Not done until reviewed.** A UI change is finished when P1 and P2 pass, and an independent
reviewer has answered P4. The author's own eye is not the review. Neither is a second look by the
same agent in a later turn — that is the same eyes with a worse memory.

Name the reviewer in the proof block. If nobody independent was available, say so and do not call
the change finished.

## Stage 4 — Ship

**Do:**
1. Run the gate, then the review gate for this domain:

   ```
   python software-factory/tools/factory.py check <repo>
   ```

   Six stages: secrets, config, privacy, docs, lint, display. A failed stage stops the line. The
   result line is the `Gate run` line of the proof block.
2. Send the change for review. A review agent may comment. A human merges.
3. Stamp the version. Write the release note.
4. Update the record: `STATUS.md`, `LESSONS_LEARNT.md`, and `UI_HISTORY.md` for a
   presentation change.
5. Publish.

**Artifact:** the pull request with the proof block, the review verdict, and the version.

**Exit condition:** merged, version stamped, record updated, evidence archived.

## Rules

1. One change per station.
2. Do not skip a stage in silence. Write "not applicable" and the reason.
3. Evidence comes before the claim. Do not write a document sentence that no artifact supports.
4. Hardware evidence comes from hardware. A green pipeline is not a panel check.
5. A failed gate stops the line. An override needs a lesson entry in the same commit.

## Short form

A one-line fix does not need this file at full length. It still needs the proof line: what
broke, what changed, how you know. Fill the short form of `templates/PROOF.md`.
