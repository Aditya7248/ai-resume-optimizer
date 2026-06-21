"""
PDF In-Place Resume Editor — PyMuPDF approach
==============================================
Core principle:
  • Open the original PDF with PyMuPDF
  • Build a map: original_text → rewritten_text (only changed content)
  • Group PDF lines into logical entries (multi-line bullets, summary paragraphs)
  • Match each entry against the text map (longest / best match first)
  • For matched entries:
      1. White-redact ALL line bounding boxes in the entry (bottom-to-top per page)
      2. Re-insert the rewritten text at the exact same position
  • Everything else is 100% untouched

Layout safety:
  - No cross-entry merging (prevents swallowing adjacent sections)
  - Edits applied bottom-to-top so upstream coordinates stay valid
  - Each insert is constrained to the original entry's height + limited overflow
"""

import copy
import os
import re
import difflib
import logging

import fitz  # PyMuPDF

OUTPUT_DIR = "/tmp/resume-optimizer"
log = logging.getLogger("pdf_inplace_engine")

# Minimum fraction of text_map entries that must match before we accept in-place edit
# How many entries must match before we accept the in-place PDF edit.
# Kept intentionally LOW so we always preserve the user's original format —
# even a few matched entries are better than regenerating the whole PDF
# in a completely different design (ReportLab fallback).
MIN_MATCH_RATE = 0.10

_BULLET_RE = re.compile(r'^[•\-\*·→⟩▪▸◆◉➢✓✔►]\s')
_SECTION_HEADER_RE = re.compile(
    r'^(?:PROFESSIONAL SUMMARY|TECHNICAL SKILLS|PROFESSIONAL EXPERIENCE|'
    r'WORK EXPERIENCE|EXPERIENCE|EDUCATION|PROJECTS|CERTIFICATIONS|'
    r'PUBLICATIONS|PUBLICATIONS & ACHIEVEMENTS|LANGUAGES|SKILLS|ACHIEVEMENTS)$',
    re.I,
)
_CATEGORY_LABEL_RE = re.compile(r'^[A-Za-z0-9 /&]+:\s*\S')
_DATE_LINE_RE = re.compile(
    r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\b',
    re.I,
)


# ── Text normalisation ─────────────────────────────────────────────────────────

def _strip_bullet(text: str) -> str:
    return re.sub(r'^[•\-\*·→⟩▪▸◆◉➢✓✔►]\s*', '', text).strip()


def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace, strip bullet chars."""
    t = _strip_bullet(text)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t


def _sanitise_for_helvetica(text: str) -> str:
    replacements = {
        # Bullet / list characters — map to ASCII hyphen so they render in Helvetica
        '•': '-',   # U+2022 BULLET (not in Latin-1 → would be dropped without this)
        '◦': '-',
        '→': '->',
        '⟩': '>',
        '▪': '-',
        '▸': '-',
        '◆': '-',
        '◉': '-',
        '➢': '->',
        '✓': 'v',
        '✔': 'v',
        '►': '-',
        '–': '-',
        '—': '--',
        '\u2019': "'",
        '\u2018': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2026': '...',
        '·': '.',
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return ''.join(c if ord(c) < 256 else '' for c in text)


def _sanitise_for_helvetica_keep_bullet(text: str) -> str:
    """
    Like _sanitise_for_helvetica but preserves • (U+2022) when the font supports it.
    Used with insert_textbox(font=TrueType_Helvetica_that_has_bullet).
    """
    replacements = {
        '◦': '-', '→': '->', '⟩': '>', '▪': '-', '▸': '-', '◆': '-',
        '◉': '-', '➢': '->', '✓': 'v', '✔': 'v', '►': '-',
        '–': '-', '—': '--',
        '\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
        '\u2026': '...', '·': '.',
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Keep • (U+2022) — drop everything else outside Latin-1
    return ''.join(c if (ord(c) < 256 or c == '\u2022') else '' for c in text)


# ── Build text map ─────────────────────────────────────────────────────────────

def _to_plain_dict(obj) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def _add_mapping(text_map: dict, original: str, rewritten: str):
    orig = (original or "").strip()
    new = (rewritten or "").strip()
    if not orig or not new or orig == new:
        return
    text_map[orig] = new
    # Also register de-bulleted version
    stripped = _strip_bullet(orig)
    if stripped and stripped != orig:
        text_map[stripped] = new


def _build_text_map(original_resume: dict, rewritten_resume: dict) -> dict:
    text_map: dict[str, str] = {}

    _add_mapping(
        text_map,
        original_resume.get("summary") or "",
        rewritten_resume.get("summary") or "",
    )

    for oe, ne in zip(
        original_resume.get("experience") or [],
        rewritten_resume.get("experience") or [],
    ):
        oe = _to_plain_dict(oe)
        ne = _to_plain_dict(ne)
        for ob, nb in zip(oe.get("bullets") or [], ne.get("bullets") or []):
            _add_mapping(text_map, ob or "", nb or "")

    for op, np_ in zip(
        original_resume.get("projects") or [],
        rewritten_resume.get("projects") or [],
    ):
        op = _to_plain_dict(op)
        np_ = _to_plain_dict(np_)
        _add_mapping(text_map, op.get("description") or "", np_.get("description") or "")
        for ob, nb in zip(op.get("bullets") or [], np_.get("bullets") or []):
            _add_mapping(text_map, ob or "", nb or "")

    return text_map


def _dedupe_text_map(text_map: dict) -> dict:
    """Collapse duplicates by normalised key, preferring the longest original."""
    by_norm: dict[str, tuple[str, str]] = {}
    for orig, new in text_map.items():
        nk = _normalise(orig)
        if not nk:
            continue
        if nk not in by_norm or len(orig) > len(by_norm[nk][0]):
            by_norm[nk] = (orig, new)
    return {orig: new for orig, new in by_norm.values()}


# ── Page line extraction ───────────────────────────────────────────────────────

def _extract_page_lines(page: fitz.Page) -> list[list[dict]]:
    """
    Extract text lines grouped by PyMuPDF block.
    Returns list-of-blocks, each block being a list of line dicts.
    """
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    pdf_blocks: list[list[dict]] = []

    for pdf_block in raw.get("blocks", []):
        if pdf_block.get("type") != 0:
            continue
        block_lines = []
        for line in pdf_block.get("lines", []):
            spans = line.get("spans", [])
            lt = " ".join(s.get("text", "") for s in spans).strip()
            if not lt:
                continue
            size = spans[0].get("size", 9.0) if spans else 9.0
            c_int = spans[0].get("color", 0) if spans else 0
            color = (
                ((c_int >> 16) & 0xFF) / 255.0,
                ((c_int >> 8) & 0xFF) / 255.0,
                (c_int & 0xFF) / 255.0,
            )
            fontname = spans[0].get("font", "") if spans else ""
            block_lines.append({
                "text": lt,
                "norm": _normalise(lt),
                "bbox": fitz.Rect(line["bbox"]),
                "size": size,
                "color": color,
                "fontname": fontname,   # original font name, used to restore •
            })
        if block_lines:
            pdf_blocks.append(block_lines)

    return pdf_blocks


_JOB_HEADER_RE = re.compile(
    r'^[A-Z][A-Za-z0-9 &.,\']+\s*[—–]\s*[A-Z]'  # "Company — Title" (both sides capitalised)
)


def _is_entry_boundary(line: dict, prev_line: dict | None) -> bool:
    """Return True when this line starts a new logical entry."""
    text = line["text"].strip()
    if not text:
        return False
    if _BULLET_RE.match(text):
        return True
    if _SECTION_HEADER_RE.match(text):
        return True
    if _CATEGORY_LABEL_RE.match(text):
        return True
    if prev_line is None:
        return True
    # Job-header lines like "Occams Advisory — AI Software Engineer"
    # Require line to start with Capital AND have em/en dash with Capital after it.
    # This prevents continuation lines with mid-sentence dashes ("→ Gmail response) — zero...")
    # from being treated as new entries.
    if _JOB_HEADER_RE.match(text) and len(text) < 120:
        return True
    if _DATE_LINE_RE.match(text):
        return True
    # Only split on a large vertical gap (clearly a different paragraph/section)
    if line["bbox"].y0 - prev_line["bbox"].y1 > 20:
        return True
    return False


def _segment_block(lines: list[dict]) -> list[list[dict]]:
    """Group lines in a block into logical entries (bullet = one entry)."""
    if not lines:
        return []
    entries: list[list[dict]] = []
    current: list[dict] = []
    for ln in lines:
        if current and _is_entry_boundary(ln, current[-1]):
            entries.append(current)
            current = [ln]
        else:
            current.append(ln)
    if current:
        entries.append(current)
    return entries


def _entry_text(entry: list[dict]) -> str:
    return " ".join(ln["text"] for ln in entry)


def _entry_norm(entry: list[dict]) -> str:
    return _normalise(_entry_text(entry))


# ── Page analysis ──────────────────────────────────────────────────────────────

def _make_group(entry: list[dict], replacement: str) -> dict:
    rects = [ln["bbox"] for ln in entry]
    x0 = min(r.x0 for r in rects)
    y0 = rects[0].y0
    x1 = max(r.x1 for r in rects) + 5
    y1 = rects[-1].y1
    bullet_m = re.match(r'^([•\-\*·→⟩▪▸◆◉➢✓✔►]\s*)', entry[0]["text"])
    fontsize = entry[0]["size"]
    return {
        "replacement": replacement,
        "original_text": _entry_text(entry),
        "line_rects": rects,
        "insert_rect": fitz.Rect(x0, y0, x1, y1),
        "fontsize": fontsize,
        "color": entry[0]["color"],
        "leading_bullet": bullet_m.group(1) if bullet_m else "",
        "orig_fontname": entry[0].get("fontname", ""),   # for bullet character rendering
    }


def _analyse_page(
    page: fitz.Page,
    text_map: dict,
    globally_matched: set,
) -> list[dict]:
    """
    Match text_map keys against single entries on this page.
    No cross-entry merging to prevent layout corruption.
    Strategies: exact → prefix/suffix → fuzzy (≥0.75).
    """
    if not text_map:
        return []

    pdf_blocks = _extract_page_lines(page)

    # Flatten to single entries only (no merges)
    all_entries: list[tuple[int, int, list[dict]]] = []
    for b_idx, block in enumerate(pdf_blocks):
        for e_idx, entry in enumerate(_segment_block(block)):
            all_entries.append((b_idx, e_idx, entry))

    norm_map: dict[str, tuple[str, str]] = {
        _normalise(k): (k, v)
        for k, v in text_map.items()
    }

    used: set[tuple[int, int]] = set()
    groups: list[dict] = []

    # Process longest keys first → greedy longest match
    sorted_norm_keys = sorted(
        (nk for nk in norm_map if nk not in globally_matched),
        key=len,
        reverse=True,
    )

    for norm_key in sorted_norm_keys:
        _, replacement = norm_map[norm_key]

        # ── Strategy A: exact normalised match ──
        best: tuple[float, int, int, list[dict]] | None = None
        for b_idx, e_idx, entry in all_entries:
            if (b_idx, e_idx) in used:
                continue
            en = _entry_norm(entry)
            if en == norm_key:
                score = 1.0
                if best is None or score > best[0] or (score == best[0] and len(entry) > len(best[3])):
                    best = (score, b_idx, e_idx, entry)

        if not best:
            # ── Strategy B: prefix or suffix containment ──
            key_len = len(norm_key)
            for b_idx, e_idx, entry in all_entries:
                if (b_idx, e_idx) in used:
                    continue
                en = _entry_norm(entry)
                if not en:
                    continue
                if norm_key.startswith(en) or en.startswith(norm_key):
                    ratio = min(len(en), key_len) / max(len(en), key_len)
                    if ratio >= 0.65:
                        if best is None or ratio > best[0]:
                            best = (ratio, b_idx, e_idx, entry)

        if not best:
            # ── Strategy B2: strict leading-prefix match ──────────────────────
            # Handles multi-sentence paragraphs (e.g. the summary) where the AI
            # parser extracted only the first sentence as the key but the PDF
            # contains the full paragraph.  If the PDF entry starts with our
            # ENTIRE key (strong signal), accept it regardless of length ratio.
            if len(norm_key) >= 60:  # only for substantial keys
                for b_idx, e_idx, entry in all_entries:
                    if (b_idx, e_idx) in used:
                        continue
                    en = _entry_norm(entry)
                    if not en:
                        continue
                    if en.startswith(norm_key):
                        log.debug(
                            "[pdf_inplace] leading-prefix match: %.50s", norm_key[:50]
                        )
                        if best is None or len(entry) > len(best[3]):
                            best = (0.88, b_idx, e_idx, entry)

        if not best:
            # ── Strategy C: fuzzy (SequenceMatcher) ──
            for b_idx, e_idx, entry in all_entries:
                if (b_idx, e_idx) in used:
                    continue
                en = _entry_norm(entry)
                if not en:
                    continue
                ratio = difflib.SequenceMatcher(None, norm_key, en).ratio()
                if ratio >= 0.75:
                    if best is None or ratio > best[0]:
                        best = (ratio, b_idx, e_idx, entry)
                    if ratio > 0.95:
                        break

        if best:
            score, b_idx, e_idx, entry = best
            if score < 1.0:
                log.debug(
                    "[pdf_inplace] fuzzy match (%.0f%%): %.50s",
                    score * 100, _entry_text(entry)[:50],
                )
            groups.append(_make_group(entry, replacement))
            used.add((b_idx, e_idx))
            globally_matched.add(norm_key)

    return groups


# ── Font extraction helper ─────────────────────────────────────────────────────

def _extract_font_for_insertion(doc: fitz.Document, page: fitz.Page, orig_fontname: str) -> "fitz.Font | None":
    """
    Extract the embedded font used by the original text and return it as a
    fitz.Font object so we can insert text (including • U+2022) in the same font.

    The key insight: if the PDF originally displayed •, the font's bytes MUST
    contain that glyph. Extracting and reusing the same font guarantees rendering.
    """
    if not orig_fontname:
        return None
    # PDF subset fonts have names like "ABCDEF+HelveticaNeue"; strip the prefix
    clean_name = re.sub(r'^[A-Z]{6}\+', '', orig_fontname)
    try:
        for xref, ext, name, enc, ref in page.get_fonts():
            page_clean = re.sub(r'^[A-Z]{6}\+', '', name)
            if page_clean == clean_name or name == orig_fontname:
                font_data = doc.extract_font(xref)
                if font_data and len(font_data) > 3 and font_data[3]:
                    return fitz.Font(fontbuffer=font_data[3])
    except Exception:
        pass
    return None


# ── Apply edits to a page ──────────────────────────────────────────────────────

def _apply_page(page: fitz.Page, groups: list[dict]):
    """
    Step 1: Redact ALL matched entries at once (single apply_redactions call).
    Step 2: Insert replacements top-to-bottom with safe_bottom constraints.

    Redacting all at once then inserting top-to-bottom ensures:
    - Inserted text appears in the content stream in reading order (top-to-bottom),
      so pdftotext and ATS parsers extract content in the correct sequence.
    - safe_bottom prevents each insert from overflowing into the next entry's space.
    """
    if not groups:
        return

    page_rect = page.rect
    # Top-to-bottom for insertion ordering
    sorted_groups = sorted(groups, key=lambda g: (g["insert_rect"].y0, g["insert_rect"].x0))

    # ── Step 1: redact the full original extent of every matched entry ──────────
    for group in sorted_groups:
        for rect in group["line_rects"]:
            r = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 6, rect.y1 + 1)
            page.add_redact_annot(r, fill=(1, 1, 1))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    # ── Pre-compute safe_bottom from ALL text on the page ──────────────────────
    # Collect y0 of every text line on the page (original + matched groups).
    # This prevents inserted text from overflowing into unchanged original lines
    # (e.g. tech-stack lines between bullets) that are not in sorted_groups.
    all_line_y0: list[float] = []
    raw_page_text = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for blk in raw_page_text.get("blocks", []):
        if blk.get("type") != 0:
            continue
        for ln in blk.get("lines", []):
            all_line_y0.append(ln["bbox"][1])   # y0 of each line

    def _safe_bottom_for(ins: fitz.Rect, matched_y1: float) -> float:
        """Return the y0 of the first page line STRICTLY below this entry."""
        sb = page_rect.height - 10
        for ly in sorted(all_line_y0):
            if ly > matched_y1 + 1:
                sb = ly - 1
                break
        return sb

    # ── Step 2: insert top-to-bottom with safe_bottom ─────────────────────────
    for idx, group in enumerate(sorted_groups):
        ins = group["insert_rect"]
        fontsize = max(6.5, min(group["fontsize"], 12.0))
        color = group["color"]

        bullet = group["leading_bullet"]
        if not bullet and _BULLET_RE.match(group["original_text"]):
            bullet = "- "
        body = _strip_bullet(group["replacement"])

        # safe_bottom = first text line below this entry (from all page text, not just matched groups)
        safe_bottom = _safe_bottom_for(ins, ins.y1)

        original_h = ins.y1 - ins.y0
        # No extra overflow — each entry uses exactly its original allocated height.
        # If new text is longer, font shrinks to fit (controlled by ±15% bullet constraint).
        max_h = min(original_h, safe_bottom - ins.y0)
        expanded = fitz.Rect(ins.x0, ins.y0 - 1, ins.x1, ins.y0 + max(max_h, fontsize + 2))

        # If the original used a bullet character that base Helvetica can't render (•),
        # try to find a font that has the glyph.
        orig_font = None
        font_to_use = None
        full_text = ""
        raw_text = ""
        has_unicode_bullet = bullet and any(ord(c) > 127 for c in bullet)
        if has_unicode_bullet:
            orig_font = _extract_font_for_insertion(page.parent, page, group.get("orig_fontname", ""))

        if has_unicode_bullet:
            # For unicode bullets (•), use a font that actually has the glyph.
            # First try to extract the original embedded font from the PDF.
            # Fall back to the system TrueType Helvetica (which has •).
            font_to_use = orig_font
            if font_to_use is None:
                try:
                    font_to_use = fitz.Font("Helvetica")   # system TrueType, has •
                    if not font_to_use.has_glyph(0x2022):
                        font_to_use = None
                except Exception:
                    font_to_use = None

        # Use insert_textbox for ALL cases — it correctly clips text to the rect boundary.
        # TextWriter.fill_textbox does NOT clip and causes text to overflow into adjacent
        # content. insert_textbox is the only reliable clipping approach.
        #
        # For unicode bullets (•): register the TrueType font with the page so that
        # insert_textbox can render • correctly (base "helv" font can't render U+2022).
        if font_to_use is not None:
            text_to_insert = _sanitise_for_helvetica_keep_bullet(bullet + body)
            # Register the TrueType font with this page so insert_textbox can use it
            try:
                registered_name = f"_sys_helv_{id(page)}"
                page.insert_font(fontname=registered_name, fontbuffer=font_to_use.buffer)
                res = page.insert_textbox(expanded, text_to_insert, fontsize=fontsize,
                                          fontname=registered_name, color=color, align=0)
            except Exception:
                # Fallback: sanitise • → - and use built-in Helvetica
                text_to_insert = _sanitise_for_helvetica(bullet + body)
                registered_name = "helv"
                res = page.insert_textbox(expanded, text_to_insert, fontsize=fontsize,
                                          color=color, align=0)
        else:
            text_to_insert = _sanitise_for_helvetica(bullet + body)
            registered_name = "helv"
            res = page.insert_textbox(expanded, text_to_insert, fontsize=fontsize,
                                      color=color, align=0)

        if res < 0:
            for try_sz in [fontsize - 0.5, fontsize - 1.0, fontsize - 1.5,
                           fontsize - 2.0, 7.5, 7.0, 6.5, 6.0]:
                if try_sz < 5.5:
                    break
                if registered_name != "helv":
                    res = page.insert_textbox(expanded, text_to_insert, fontsize=try_sz,
                                              fontname=registered_name, color=color, align=0)
                else:
                    res = page.insert_textbox(expanded, text_to_insert, fontsize=try_sz,
                                              color=color, align=0)
                if res >= 0:
                    break

        if res < 0:
            log.warning(
                "[pdf_inplace] overflow — could not fit text (fontsize=%.1f, rect=%s, text=%.40s)",
                fontsize, expanded, text_to_insert,
            )


# ── Content-stream reading-order normalisation ────────────────────────────────

# Matches a COMPLETE text-object graphics block: q [preamble] BT [text ops] ET Q
# The preamble often contains a coordinate-matrix operator (cm) for positioning.
# Non-greedy so each block is captured separately.
# Negative lookahead in preamble prevents the regex from crossing into the next block's BT.
_TEXT_BLOCK_RE = re.compile(
    rb'q[ \t\r\n]+'                     # opening graphics-state save
    rb'(?:(?!BT[ \t\r\n]).)*'           # preamble: any bytes except start of BT operator
    rb'BT[ \t\r\n]+'                    # begin text
    rb'.*?'                             # text operators (non-greedy)
    rb'ET[ \t\r\n]+'                    # end text
    rb'Q',                              # closing graphics-state restore
    re.DOTALL,
)

# Extracts the 'f' (Y) component from a text-matrix operator: a b c d e f Tm
_TM_Y_RE = re.compile(
    rb'[-+]?\d*\.?\d+\s+'   # a
    rb'[-+]?\d*\.?\d+\s+'   # b
    rb'[-+]?\d*\.?\d+\s+'   # c
    rb'[-+]?\d*\.?\d+\s+'   # d
    rb'[-+]?\d*\.?\d+\s+'   # e
    rb'([-+]?\d*\.?\d+)\s+' # f  ← Y coordinate in current coordinate space
    rb'Tm',
)

# Extracts the Y-translation from a coordinate-matrix operator: a b c d e f cm
_CM_Y_RE = re.compile(
    rb'[-+]?\d*\.?\d+\s+'   # a
    rb'[-+]?\d*\.?\d+\s+'   # b
    rb'[-+]?\d*\.?\d+\s+'   # c
    rb'[-+]?\d*\.?\d+\s+'   # d
    rb'[-+]?\d*\.?\d+\s+'   # e
    rb'([-+]?\d*\.?\d+)\s+' # f  ← Y translation (captured)
    rb'cm',
)


def _normalize_page_reading_order(page: fitz.Page) -> None:
    """
    Rebuild the page content stream so that ALL text blocks appear in
    top-to-bottom (reading) order.

    PyMuPDF's insert_textbox always appends to the end of the content stream,
    so inserted text appears AFTER the original remaining text in the stream
    even when its Y position is higher on the page.  pdftotext, many ATS
    parsers, and PDF accessibility tools read the stream sequentially, giving
    wrong extraction order.

    Fix: after all page edits, merge all content streams, extract every
    BT...ET text block with its PDF-coordinate Y value, remove them from
    their current positions, and re-append them in descending-Y order
    (highest PDF Y = topmost on page = first in reading order).
    The non-text content (drawings, backgrounds, redaction rects) stays in
    its original order so visual rendering is unchanged.
    """
    doc: fitz.Document = page.parent
    page.clean_contents(sanitize=True)
    raw = page.read_contents()
    if len(raw) < 10:
        return

    # Collect all text blocks with their TRUE page-Y positions.
    #
    # Each block is: q [preamble possibly containing cm] BT [text ops] ET Q
    #
    # Original PDF content: q 1 0 0 1 X cm_Y cm [setup] BT 1 0 0 1 x tm_Y Tm [text] ET Q
    #   true_Y = cm_Y + tm_Y
    #
    # PyMuPDF-inserted content (no cm, absolute coords):
    #   q [setup] BT 1 0 0 1 x Y_abs Tm [text] ET Q
    #   true_Y = Y_abs  (cm_y = 0)
    #
    # Since the FULL block is captured, both cm and Tm are searched inside it.
    blocks: list[tuple[float, int, int, bytes]] = []
    for m in _TEXT_BLOCK_RE.finditer(raw):
        blk = m.group(0)
        cm = _CM_Y_RE.search(blk)   # cm is in the preamble, INSIDE the block
        tm = _TM_Y_RE.search(blk)   # Tm is in the BT...ET section, INSIDE the block
        cm_y = float(cm.group(1)) if cm else 0.0
        tm_y = float(tm.group(1)) if tm else 0.0
        y_true = cm_y + tm_y
        blocks.append((y_true, m.start(), m.end(), blk))

    if len(blocks) <= 1:
        return  # Nothing to reorder

    # Check if already in descending-Y order (= reading order)
    ys = [b[0] for b in blocks]
    if ys == sorted(ys, reverse=True):
        return

    # Strip all text blocks from the stream (keep drawings, rects, etc.)
    non_text = b""
    prev = 0
    for _, start, end, _ in sorted(blocks, key=lambda b: b[1]):
        non_text += raw[prev:start]
        prev = end
    non_text += raw[prev:]

    # Re-append text blocks in descending-Y order
    sorted_blocks = sorted(blocks, key=lambda b: b[0], reverse=True)
    new_stream = non_text.rstrip() + b"\n" + b"\n".join(blk.strip() for _, _, _, blk in sorted_blocks)

    # Update the content stream in-place via its xref
    xrefs = page.get_contents()
    if not xrefs:
        return
    doc.update_stream(xrefs[0], new_stream)
    log.debug("[pdf_inplace] page reading order normalised (%d text blocks)", len(blocks))


# ── Skills category injection ──────────────────────────────────────────────────

_CATEGORY_HINTS: list[tuple[list[str], list[str]]] = [
    (["langgraph", "langchain", "langsmith", "crewai", "autogen"],
     ["agentic", "orchestration", "langchain", "agent"]),
    (["azure ai", "azure openai", "azure ml"],
     ["cloud", "azure", "deployment", "aws"]),
    (["system design", "distributed systems", "architecture"],
     ["agentic", "orchestration", "system", "architecture", "cloud"]),
    (["openai", "gpt-4", "chatgpt"],
     ["llm", "genai", "openai"]),
    (["pytorch", "tensorflow", "keras", "sklearn", "scikit"],
     ["ml", "inference", "pytorch", "tensorflow"]),
    (["docker", "kubernetes", "k8s"],
     ["cloud", "deployment", "docker"]),
    (["sql", "postgres", "mysql", "mongodb"],
     ["data", "storage", "sql", "database"]),
]


def _best_category_for_skill(skill: str, category_lines: list[str]) -> str | None:
    skill_lower = skill.lower()
    best_hints: list[str] = []
    for skill_kws, cat_kws in _CATEGORY_HINTS:
        if any(kw in skill_lower for kw in skill_kws):
            best_hints = cat_kws
            break

    if not best_hints:
        return max(category_lines, key=len) if category_lines else None

    best_line = None
    best_score = -1
    for line in category_lines:
        score = sum(1 for h in best_hints if h in line.lower())
        if score > best_score:
            best_score = score
            best_line = line

    return best_line if best_score > 0 else (category_lines[0] if category_lines else None)


def _build_skills_text_map(doc: fitz.Document, skills_to_add: list[str]) -> dict:
    """
    Scan PDF for skill-category lines and build replacements that append each
    skill to the correct category. Each skill is matched independently against
    the original (pre-append) category lines to prevent all skills piling onto
    one line.
    """
    if not skills_to_add:
        return {}

    # Collect candidate category lines from the PDF.
    # A valid skills category line looks like: "Tools: Power BI, SQL, Python"
    # An INVALID match would be: "Dashboard Migration & Optimization: Repointed an..."
    #   (experience section header used as a bullet intro — too long a label, reads like a sentence)
    # Filters:
    #   1. Must match "Label: content" pattern
    #   2. The label part (before ":") must be ≤ 45 chars (short enough for a category name)
    #   3. The label must NOT start with a bullet character (•, -, *, etc.)
    #   4. Total line content should look like a list, not a sentence
    _EXPERIENCE_HEADER_WORDS = {
        "repointed", "migrated", "implemented", "developed", "designed",
        "built", "created", "managed", "led", "automated", "optimized",
        "collaborated", "established", "researched", "performed",
    }

    category_candidates: list[str] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for block in _extract_page_lines(page):
            for entry in _segment_block(block):
                text = _entry_text(entry).strip()
                first = entry[0]["text"].strip()
                if not (len(text) > 20 and ":" in first and _CATEGORY_LABEL_RE.match(first)):
                    continue
                # Reject if this is a bullet-prefixed line (experience bullet masquerading)
                if _BULLET_RE.match(first):
                    continue
                # Extract the label (part before ":") and validate
                label_part = first.split(":")[0].strip()
                if len(label_part) > 50:
                    continue  # Label too long — likely an experience section title
                # Reject if the content part looks like a sentence (starts with verb)
                content_after_colon = first[len(label_part) + 1:].strip().lower()
                first_word = content_after_colon.split()[0] if content_after_colon.split() else ""
                if first_word in _EXPERIENCE_HEADER_WORDS:
                    continue
                if text not in category_candidates:
                    category_candidates.append(text)

    if not category_candidates:
        log.warning("[pdf_inplace] No category lines found — skills additions skipped")
        return {}

    log.debug("[pdf_inplace] Found %d category candidate lines", len(category_candidates))

    # additions maps original_line → updated_line (accumulates all skills for that line)
    additions: dict[str, str] = {}

    for skill in skills_to_add:
        # Skip if already present in any candidate
        if any(skill.lower() in c.lower() for c in category_candidates):
            log.debug("[pdf_inplace] skill already present, skipping: %s", skill)
            continue

        # Always search against the ORIGINAL candidate lines for routing,
        # but write the updated text into additions
        target_original = _best_category_for_skill(skill, category_candidates)
        if not target_original:
            log.warning("[pdf_inplace] No suitable category line found for skill: %s", skill)
            continue

        current_text = additions.get(target_original, target_original)
        additions[target_original] = current_text.rstrip(". ") + ", " + skill
        log.info(
            "[pdf_inplace] skills_add: '%s' → appending to: %.60s",
            skill, target_original,
        )

    return additions


# ── Main entry point ──────────────────────────────────────────────────────────

def inject_into_pdf_inplace(
    resume_bytes: bytes,
    original_resume: dict,
    rewritten_resume: dict,
    session_id: str,
    skills_to_add: list[str] | None = None,
) -> dict:
    """
    Edit the original PDF in-place using PyMuPDF.
    Returns {"docx": None, "pdf": "optimized_resume.pdf", "match_rate": float}.
    """
    out_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(out_dir, exist_ok=True)
    pdf_filename = "optimized_resume.pdf"
    pdf_path = os.path.join(out_dir, pdf_filename)

    if hasattr(original_resume, "model_dump"):
        original_resume = original_resume.model_dump()
    if hasattr(rewritten_resume, "model_dump"):
        rewritten_resume = rewritten_resume.model_dump()

    text_map = _dedupe_text_map(_build_text_map(original_resume, rewritten_resume))

    # Skills injection
    if skills_to_add:
        _tmp_doc = fitz.open(stream=resume_bytes, filetype="pdf")
        skills_map = _build_skills_text_map(_tmp_doc, skills_to_add)
        _tmp_doc.close()
        if skills_map:
            log.info(
                "[pdf_inplace] skills_to_add: %d skill(s), %d category line(s) updated",
                len(skills_to_add), len(skills_map),
            )
            text_map.update(skills_map)

    text_map = _dedupe_text_map(text_map)

    log.info("[pdf_inplace] text_map built — %d entries to replace", len(text_map))
    for i, (orig, new) in enumerate(text_map.items(), 1):
        log.debug("  [%02d] ORIG: %.70s", i, orig)
        log.debug("       NEW : %.70s", new)

    if not text_map:
        with open(pdf_path, "wb") as f:
            f.write(resume_bytes)
        log.info("[pdf_inplace] No changes — saving original PDF unchanged")
        return {"docx": None, "pdf": pdf_filename, "match_rate": 1.0}

    doc = fitz.open(stream=resume_bytes, filetype="pdf")
    total_pages = len(doc)
    changed_pages = 0
    globally_matched: set[str] = set()
    norm_keys_total = {_normalise(k) for k in text_map}

    for page_num in range(total_pages):
        page = doc[page_num]
        groups = _analyse_page(page, text_map, globally_matched)

        log.info(
            "[pdf_inplace] Page %d/%d — matched %d entries | running total %d/%d",
            page_num + 1, total_pages, len(groups),
            len(globally_matched), len(norm_keys_total),
        )
        for g in groups:
            log.debug(
                "  ✓ y=%.0f-%.0f  repl: %.60s",
                g["insert_rect"].y0, g["insert_rect"].y1, g["replacement"],
            )

        if groups:
            _apply_page(page, groups)
            _normalize_page_reading_order(page)
            changed_pages += 1

    doc.save(pdf_path, garbage=4, deflate=True)
    doc.close()

    match_rate = len(globally_matched) / len(norm_keys_total) if norm_keys_total else 1.0
    unmatched = norm_keys_total - globally_matched
    if unmatched:
        log.warning(
            "[pdf_inplace] %d unmatched entries: %s",
            len(unmatched),
            " | ".join(list(unmatched)[:3]) + ("..." if len(unmatched) > 3 else ""),
        )

    log.info(
        "[pdf_inplace] Complete — %d/%d pages, %d/%d entries replaced (%.0f%%) → %s",
        changed_pages, total_pages,
        len(globally_matched), len(norm_keys_total),
        match_rate * 100, pdf_path,
    )
    return {"docx": None, "pdf": pdf_filename, "match_rate": match_rate}
