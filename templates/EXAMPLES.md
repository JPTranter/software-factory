# Proof Blocks — Three Real Examples

These blocks come from commits in this project set. Fields shown as `<not archived>` were not
recorded at the time. The block shows the gap instead of filling it with a guess. That is the
point of the format.

---

## 1. A firmware change with numbers

eClock, `a997c64`, 2026-09-05. The battery sample held the CPU for 10 ms per read.

```markdown
## Proof

**Change:** The battery ADC waits 50 µs for the divider to settle, not 10 ms, so each battery
read is about 200 times shorter.
**Base commit:** <not archived>  **Station:** none — pre-factory
**Gate run:** `pio run -e xiao_nrf52840_plus` → SUCCESS

### Before

`delay(10); // stabilize` — 10 ms, blocking, on every battery read.

### After

`delayMicroseconds(50); // RC settle time (<10us for 1M divider + small cap)` — 50 µs.

### Numbers

| Measure | Before | After | How measured |
| --- | --- | --- | --- |
| Settle wait per read | 10 ms | 50 µs | Code constant; RC time from the divider values |
| Standby current | <not archived> | <not archived> | Not measured on the bench for this commit |

### Not proved

The standby current was not measured. The RC time is a calculation, not a scope trace. Safe
because the divider is 1 MΩ with a small capacitor, which settles well inside 50 µs, and the
reading agreed with USB power in the same session.

### Lesson

Recorded in `docs/lessons/LESSONS_LEARNT.md` in the same commit.
```

**What this example shows:** a real number pair, and an honest hole where the bench
measurement should be.

---

## 2. A presentation change with a render

ChromaWOTD, `88c465a`, 2026-09-22. `kVerseMaxH` went from 82 to 93, so the text area reaches the
footer row.

```markdown
## Proof

**Change:** The verse box uses the footer row, so a long verse keeps whole lines instead of
dropping one.
**Base commit:** 88c465a^  **Station:** none — pre-factory
**Gate run:** `python tools/verify_all.py` → render ledger verified, layout invariants pass

### Before

Host render at the old limit. The autosize ladder for four lengths is archived at
`docs/images/history/layout_landscape_autosize_4lengths.png`. The boundary case is at
`docs/images/history/layout_landscape_autosize_boundary55.png`.

### After

`<not archived as a single before/after pair>` — the change is covered by the wrap tests
(`firmware/test/tests/test_text.cpp`, 30 lines changed) and the autosize fixture.

### Numbers

| Measure | Before | After | How measured |
| --- | --- | --- | --- |
| `kVerseMaxH` | 82 px | 93 px | `firmware/src/verse_display.cpp` |
| Cases in the wrap test | <not archived> | +30 lines | Test diff |

### Evidence locations

- Ledger: `docs/images/layout_landscape.png` — byte-compared on every `verify_all.py` run
- History: `docs/images/history/layout_landscape_autosize_*.png` — the renders the size ladder
  was decided from

### Not proved

Not observed on the panel in this commit. The ledger render comes from the host build, which
uses the 5×7 fallback font. The device-font render is the one a type decision should use — see
`docs/UI_HISTORY.md` for why that distinction matters.
```

**What this example shows:** the three image locations used correctly, and a limit named
instead of hidden.

---

## 3. A tooling change, short form

ApolloMatrix, `3caee93`, 2026-09-26. The privacy gate existed but never ran in CI.

```markdown
## Proof (short)

**Broke:** The privacy gate was in the tree, but neither the harness nor CI called it. It had
never failed, because it had never run.
**Changed:** The harness calls the gate as its first step, CI calls the harness, and the lesson
records the failure mode. The harness also names a missing Python package instead of dying four
steps later.
**How I know:** `test/run_tests.sh` → `== privacy (secrets, home paths, image metadata — tracked +
untracked) ==` runs first, and the run fails when a planted home path is added.
```

**What this example shows:** the short form for a change that has no image and no number. Three
lines and a command. That is enough.
