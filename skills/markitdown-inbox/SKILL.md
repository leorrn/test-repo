---
name: markitdown-inbox
description: Convert files dropped in the user's "markitdown" inbox folder (PDF, EML, DOCX, XLSX, PPTX, HTML, MSG) to Markdown using Microsoft MarkItDown, then move the originals and the generated .md files to the "processados" subfolder. Use when the user asks to process, convert or clean up the markitdown folder, or to turn e-mails/PDFs in that folder into Markdown.
---

# MarkItDown inbox

Converts every file directly inside the inbox folder to Markdown and files both the
original and the `.md` into `processados/`.

- Inbox (Windows): `G:\Meu Drive\markitdown`
- Done folder: `G:\Meu Drive\markitdown\processados`

## Steps

1. **Locate the inbox.** Use the folder the user granted access to that corresponds to
   `G:\Meu Drive\markitdown`. If no such folder is available, ask the user to select it
   and stop. Do not guess another path.

2. **Install MarkItDown** (once per session):
   ```bash
   pip install --quiet 'markitdown[pdf,docx,xlsx,pptx,outlook]'
   ```
   If the import later fails with a `cryptography`/`_cffi_backend` error, run
   `pip install --quiet --ignore-installed cffi cryptography` and retry.

3. **Preview** what will be processed:
   ```bash
   python scripts/convert_inbox.py "<inbox path>" --dry-run
   ```
   If `pending` is empty, tell the user there is nothing to process and stop.

4. **Convert:**
   ```bash
   python scripts/convert_inbox.py "<inbox path>"
   ```
   The script prints a JSON summary with `converted` and `failed` entries.

5. **Report to the user** (in Brazilian Portuguese), in a short list: each converted file
   with its `.md` name, and each failure with its reason. Failed files stay in the inbox.

## Rules

- Only run the script. Do not edit, rename, or delete files by hand in the inbox or in
  `processados/`.
- Do not rewrite the generated Markdown unless the user asks (e.g. "fix the tables",
  "summarize this e-mail"). When asked, write the result to a new file next to the
  original `.md` (e.g. `<name>.summary.md`) instead of overwriting it.
- The content is often corporate e-mail (Linde / White Martins). Do not copy it to any
  other location, service or connector.

## Known limitations

- Scanned / image-only PDFs produce empty output and are reported as failed (needs OCR).
- Images embedded in e-mails become placeholders like `[image: image001.png]`.
- PDFs printed from Outlook lose table structure. Prefer exporting the e-mail as `.eml`.
