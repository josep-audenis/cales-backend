# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# LLM Wiki Schema

This repo is an **LLM-maintained wiki**. You (the LLM) own the `wiki/` layer. The human curates sources in `raw/` and asks questions.

## Layers

- `raw/` — immutable source documents (PDFs, articles, notes, images). Never modify.
- `wiki/` — markdown pages you write and maintain (summaries, entities, concepts, syntheses).
- `INDEX.md` — content catalog. Updated on every ingest.
- `LOG.md` — chronological append-only journal of ingests/queries/lint passes.
- `CLAUDE.md` — this file. The schema. Co-evolve with the user.

## Conventions

- File names: `kebab-case.md` inside `wiki/`. Entity pages capitalize proper nouns (`wiki/entities/Hugging-Face.md`).
- Subfolders: `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`.
- Cross-links: use Obsidian-style `[[Page-Name]]` links. Link liberally — dangling links mark future work.
- Frontmatter (YAML) on every wiki page:
  ```yaml
  ---
  type: source | entity | concept | synthesis
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  sources: [source-slug-1, source-slug-2]
  tags: [tag1, tag2]
  ---
  ```
- Citations: when claims come from a source, link to its source page (`[[sources/smartbuy-compras-es]]`).

## Operations

### Ingest

When the user drops a file in `raw/` and says "ingest":

1. Read the source fully.
2. Discuss key takeaways with the user before writing.
3. Create `wiki/sources/<slug>.md` — summary, key claims, quotes, open questions.
4. Update or create relevant `wiki/entities/` and `wiki/concepts/` pages.
5. Flag contradictions with existing pages in a `## Contradictions` section.
6. Update `INDEX.md`.
7. Append entry to `LOG.md`: `## [YYYY-MM-DD] ingest | <Source Title>`.

A single ingest may touch 10–15 pages. That is expected.

### Query

When the user asks a question:

1. Read `INDEX.md` first to find candidate pages.
2. Drill into relevant wiki pages. Avoid re-reading `raw/` unless wiki is insufficient.
3. Answer with citations to wiki pages.
4. If answer is non-trivial, **offer to file it back** as `wiki/syntheses/<slug>.md` so the exploration compounds.
5. Append entry to `LOG.md`: `## [YYYY-MM-DD] query | <Question>`.

### Lint

When the user asks "lint" or periodically:

- Find contradictions between pages.
- Find stale claims newer sources have superseded.
- Find orphan pages (no inbound `[[links]]`).
- Find concepts mentioned but lacking their own page.
- Suggest missing cross-references.
- Suggest new sources / web searches that would fill data gaps.
- Append entry to `LOG.md`: `## [YYYY-MM-DD] lint | <summary>`.

## Workflow rules

- Never modify `raw/`.
- Never write to the wiki without telling the user which pages will change.
- Prefer updating existing pages over creating new ones.
- Keep pages short and linked rather than long and self-contained.
- If unsure where info belongs, ask.
