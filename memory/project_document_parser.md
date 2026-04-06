---
name: DocumentParserBot — branch and coordination notes
description: When building DocumentParserBot, use fla's feature/document-model branch and a matching libertas branch
type: project
---

When working on aabtzu/fiat-lux-agents#21 (DocumentParserBot):

- **fla**: switch to `feature/document-model` branch — `DocumentExtractor` (text → structured JSON) already exists there; build the file dispatch layer on top of it
- **libertas**: create a matching branch (e.g. `document_parser_integration`) to wire up `upload_plan_handler` in `agents/create/handler.py` as a thin subclass once fla's bot lands

**Why:** The branch has existing work that must not be duplicated or lost. `DocumentExtractor` handles text → JSON; what's missing is the file dispatch (PDF, image, XLSX, CSV) layer tracked in #21.

**How to apply:** Any time the conversation turns to DocumentParserBot, document extraction, or the upload plan handler refactor — remind to coordinate branches across both repos.
