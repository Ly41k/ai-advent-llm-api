"""Give the model short IDs; extract final quotations from trusted chunk text."""

import re

from evidence import python_filenames


def source_metadata(hit):
    # A numbered source directory identifies a lesson, not an execution date.
    match = re.search(r"(?:^|[/\\])day-(\d+)(?:-|[/\\]|$)", hit.source)
    return {"chunk_id": hit.chunk_id, "source": hit.source, "section": hit.section,
            "course_lesson": int(match.group(1)) if match else None}


def quote_structure(hit, quote):
    """Headings guide selection; metadata is never proof of operational behavior."""
    if hit.source.endswith(".py"):
        return {"heading": None, "kind": "code"}
    heading, fence = None, False
    prefix = hit.text[:hit.text.index(quote)]
    for line in prefix.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence:
            match = re.match(r"^#{1,6}\s+(.+)", line)
            if match:
                heading = match.group(1).strip()
    stripped = quote.strip()
    kind = "prose"
    if fence or stripped.startswith(("```", "~~~")):
        kind = "code"
    elif re.fullmatch(r"#{1,6}\s+[^\n]+", stripped):
        kind = "heading"
    elif re.fullmatch(r"(?:[-*]\s+)?\[[^\]]+\]\([^\n]+\)[.!]?", stripped):
        kind = "reference"
    elif stripped.startswith("|"):
        kind = "table"
    elif re.match(r"(?:[-*]|\d+[.)])\s+", stripped):
        kind = "list"
    return {"heading": heading, "kind": kind}


def build_catalog(hits):
    catalog = {}
    for number, hit in enumerate(hits, 1):
        seen, fragments = set(), []

        def add(value):
            # Trimming outer whitespace still produces a literal substring.
            value = value.strip()
            if 12 <= len(value) <= 1600 and value not in seen:
                seen.add(value)
                fragments.append(value)

        for paragraph in re.split(r"\n[ \t]*\n", hit.text):
            if len(paragraph.strip()) <= 1600:
                add(paragraph)
            else:
                # Partition long blocks on source line boundaries where possible.
                block = ""
                for line in paragraph.splitlines(keepends=True):
                    if block and len(block + line) > 1500:
                        add(block)
                        block = ""
                    if len(line) > 1500:
                        for start in range(0, len(line), 1500):
                            add(line[start:start + 1500])
                    else:
                        block += line
                add(block)
            # Markdown tables/bullets/commands also have useful individual lines.
            if ("\n" in paragraph and not hit.source.endswith(".py") and
                    len(paragraph.splitlines()) <= 6 and not paragraph.strip().startswith("```")):
                for line in paragraph.splitlines():
                    add(line)
        for index, quote in enumerate(fragments, 1):
            catalog[f"q{number}_{index}"] = {"chunk_id": hit.chunk_id, "quote": quote,
                                           **quote_structure(hit, quote)}
    return catalog


def catalog_context(hits, catalog, compact=False):
    if compact:
        # Text/IDs and source identity suffice for evidence selection. Detailed
        # structural metadata remains in the trace rather than repeated at every
        # generation stage. Omit chunks without selected evidence.
        return [{**source_metadata(hit),
                 "quotes": [{"quote_id": qid, "text": row["quote"]}
                            for qid, row in catalog.items() if row["chunk_id"] == hit.chunk_id]}
                for hit in hits if any(row["chunk_id"] == hit.chunk_id for row in catalog.values())]
    return [{**source_metadata(hit),
             "quotes": [{"quote_id": quote_id, "text": row["quote"],
                         "heading": row["heading"], "kind": row["kind"],
                         "python_files": sorted(python_filenames(row["quote"]))}
                        for quote_id, row in catalog.items() if row["chunk_id"] == hit.chunk_id]}
            for hit in hits]
