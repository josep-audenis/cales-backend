# cales-backend — LLM Wiki

Personal knowledge base maintained by an LLM agent.

## Layout

- `raw/` — source documents (immutable).
- `wiki/` — LLM-written markdown pages.
  - `sources/` — per-source summaries.
  - `entities/` — people, orgs, products, places.
  - `concepts/` — ideas, definitions, techniques.
  - `syntheses/` — cross-source analyses, comparisons, answers.
- `CLAUDE.md` — schema / instructions for the LLM agent.
- `INDEX.md` — content catalog.
- `LOG.md` — chronological journal.

## Usage

1. Drop a source into `raw/`.
2. Tell the agent: "ingest `raw/<file>`".
3. Browse the wiki in Obsidian while the agent edits.
4. Ask questions. File good answers back into `wiki/syntheses/`.
5. Periodically: "lint the wiki".

See `CLAUDE.md` for the full schema.
