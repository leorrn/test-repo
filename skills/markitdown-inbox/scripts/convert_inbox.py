#!/usr/bin/env python3
"""Convert every file in an inbox folder to Markdown with Microsoft MarkItDown.

For each file directly inside INBOX:
  - writes <stem>.md into DONE (default: INBOX/processados)
  - moves the original file into DONE
Files that fail to convert stay in INBOX and are reported as errors.

.eml files are handled here because MarkItDown has no e-mail converter:
the HTML body is extracted and converted, Outlook Safe Links are unwrapped
and inline images (cid:) are replaced by placeholders.

Prints a JSON summary on stdout. Exit code is 1 if any file failed.
"""
from __future__ import annotations

import argparse
import email
import html
import io
import json
import re
import shutil
import sys
import urllib.parse
from datetime import datetime
from email import policy
from pathlib import Path

from markitdown import MarkItDown, StreamInfo

DEFAULT_DONE_NAME = "processados"
SKIP_PREFIXES = ("~$", ".")
SKIP_SUFFIXES = {".md", ".tmp", ".ini", ".lnk", ".gdoc", ".gsheet", ".gslides"}

SAFELINK_RE = re.compile(r"https://[a-z0-9]+\.safelinks\.protection\.outlook\.com/\?[^)\s]+")
CID_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(cid:([^@)]+)(?:@[^)]*)?\)")


def unwrap_safelinks(text: str) -> str:
    def _unwrap(match: re.Match) -> str:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(match.group(0)).query)
        return query.get("url", [match.group(0)])[0]

    return SAFELINK_RE.sub(_unwrap, text)


def eml_to_markdown(path: Path, md: MarkItDown) -> str:
    with path.open("rb") as fh:
        msg = email.message_from_binary_file(fh, policy=policy.default)

    header = (
        f"<h1>{html.escape(str(msg['subject'] or path.stem))}</h1>"
        f"<p><b>From:</b> {html.escape(str(msg['from'] or ''))}<br>"
        f"<b>To:</b> {html.escape(str(msg['to'] or ''))}<br>"
        + (f"<b>Cc:</b> {html.escape(str(msg['cc']))}<br>" if msg["cc"] else "")
        + f"<b>Date:</b> {html.escape(str(msg['date'] or ''))}</p><hr>"
    )

    body_part = msg.get_body(preferencelist=("html", "plain"))
    if body_part is None:
        body_html = ""
    elif body_part.get_content_type() == "text/html":
        body_html = body_part.get_content()
    else:
        body_html = f"<pre>{html.escape(body_part.get_content())}</pre>"

    attachments = [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]
    footer = ""
    if attachments:
        items = "".join(f"<li>{html.escape(a)}</li>" for a in attachments)
        footer = f"<hr><p><b>Attachments / inline images:</b></p><ul>{items}</ul>"

    full_html = f"<html><body>{header}{body_html}{footer}</body></html>"
    result = md.convert_stream(
        io.BytesIO(full_html.encode("utf-8")),
        stream_info=StreamInfo(extension=".html", mimetype="text/html", charset="utf-8"),
    )
    text = CID_IMAGE_RE.sub(r"[image: \1]", result.text_content)
    return unwrap_safelinks(text)


def to_markdown(path: Path, md: MarkItDown) -> str:
    if path.suffix.lower() == ".eml":
        return eml_to_markdown(path, md)
    return unwrap_safelinks(md.convert(str(path)).text_content)


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return target.with_name(f"{target.stem}_{stamp}{target.suffix}")


def should_skip(path: Path) -> bool:
    return (
        not path.is_file()
        or path.name.startswith(SKIP_PREFIXES)
        or path.suffix.lower() in SKIP_SUFFIXES
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inbox", type=Path, help="Folder with files to convert")
    parser.add_argument("--done", type=Path, help=f"Destination folder (default: INBOX/{DEFAULT_DONE_NAME})")
    parser.add_argument("--dry-run", action="store_true", help="List what would be processed and exit")
    args = parser.parse_args()

    inbox: Path = args.inbox.expanduser().resolve()
    done: Path = (args.done or inbox / DEFAULT_DONE_NAME).expanduser().resolve()
    if not inbox.is_dir():
        print(json.dumps({"error": f"Inbox folder not found: {inbox}"}))
        return 2

    candidates = sorted(p for p in inbox.iterdir() if not should_skip(p))
    summary: dict = {"inbox": str(inbox), "done": str(done), "converted": [], "failed": [], "dry_run": args.dry_run}

    if args.dry_run:
        summary["pending"] = [p.name for p in candidates]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    done.mkdir(parents=True, exist_ok=True)
    md = MarkItDown()

    for src in candidates:
        try:
            text = to_markdown(src, md)
            if not text.strip():
                raise ValueError("Empty output (scanned/image-only file? needs OCR)")
            md_path = done / f"{src.stem}.md"
            if md_path.exists():
                md_path = unique_path(done / f"{src.name}.md")
            md_path.write_text(text, encoding="utf-8")
            moved_to = unique_path(done / src.name)
            shutil.move(str(src), str(moved_to))
            summary["converted"].append(
                {"source": src.name, "markdown": md_path.name, "moved_to": moved_to.name, "chars": len(text)}
            )
        except Exception as exc:  # keep going; failed files stay in the inbox
            summary["failed"].append({"source": src.name, "error": f"{type(exc).__name__}: {exc}"})

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
