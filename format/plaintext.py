from lxml import etree
import re, json, csv
from conf import *
from utils import *
from typing import Callable
from pathlib import Path
from rich.progress import track, Progress


def translate_md(path: Path, translate_fn: Callable[[str], str], verbose: bool=False):
    """
    Simple Markdown translator:
    - keeps code fences untouched
    - translates normal text lines
    - leaves headings/list markers mostly intact
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    out = []
    in_code = False

    for line in track(lines):
        stripped = line.rstrip("\n")

        # fenced code blocks
        if stripped.strip().startswith("```") or stripped.strip().startswith("~~~"):
            in_code = not in_code
            out.append(line)
            continue

        if in_code:
            out.append(line)
            continue

        if not stripped.strip():
            out.append(line)
            continue

        # preserve common markdown prefixes
        m = re.match(r"^(\s*(?:[-*+]\s+|\d+\.\s+|#{1,6}\s+|>\s+))(.+)$", stripped)
        if m:
            prefix, text = m.groups()
            translated = translate_text(text.strip(), translate_fn, verbose=verbose)
            out.append(prefix + translated + "\n")
        else:
            out.append(translate_text(stripped, translate_fn, verbose=verbose) + "\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)

def translate_latex(path: Path, translate_fn: Callable[[str], str], verbose: bool=False):
    """
    Basic LaTeX translator:
    - preserves math environments
    - preserves commands
    - translates plain text outside commands
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # protect math blocks
    protected = []

    def protect(pattern, s):
        def repl(m):
            protected.append(m.group(0))
            return f"@@PROT{len(protected)-1}@@"
        return re.sub(pattern, repl, s, flags=re.DOTALL)

    # protect common math/code environments
    text = protect(r"\$\$.*?\$\$", text)
    text = protect(r"\$.*?\$", text)
    text = protect(r"\\\[.*?\\\]", text)
    text = protect(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", text)
    text = protect(r"\\begin\{lstlisting\}.*?\\end\{lstlisting\}", text)

    # translate text segments outside commands
    parts = re.split(r"(\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{[^{}]*\})*)", text)
    out = []

    for part in track(parts):
        if not part:
            continue
        if part.startswith("\\"):
            out.append(part)
        elif part.startswith("@@PROT") and part.endswith("@@"):
            out.append(part)
        else:
            # translate only non-empty visible text
            if part.strip():
                out.append(translate_text(part, translate_fn, verbose=verbose))
            else:
                out.append(part)

    text = "".join(out)

    # restore protected blocks
    for i, chunk in enumerate(protected):
        text = text.replace(f"@@PROT{i}@@", chunk)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def translate_txt(path: Path, translate_fn: Callable[[str], str], verbose: bool=False):
	with open(path, "r", encoding="utf-8", errors="ignore") as f:
		lines = f.readlines()

	out = []
	for line in track(lines):
		stripped = line.strip()
		if stripped and clean_text(REG_CLEAN, stripped).strip():
			out.append(translate_text(line.rstrip("\n"), translate_fn, verbose=verbose) + "\n")
		else:
			out.append(line)

	with open(path, "w", encoding="utf-8", newline="") as f:
		f.writelines(out)


def translate_csv(path: Path, translate_fn: Callable[[str], str], verbose: bool=False):
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as fin:
        sample = fin.read(4096)
        fin.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(fin, dialect)

        rows = []
        for row in track(reader):
            new_row = []
            for cell in row:
                if cell and clean_text(REG_CLEAN, cell).strip():
                    new_row.append(translate_text(cell, translate_fn, verbose=verbose))
                else:
                    new_row.append(cell)
            rows.append(new_row)

    with open(path, "w", encoding="utf-8", newline="") as fout:
        writer = csv.writer(fout, dialect)
        writer.writerows(rows)


def translate_xml(path: Path, translate_fn: Callable[[str], str], verbose: bool=False):
    parser = etree.XMLParser(recover=True, remove_blank_text=False)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    for el in track(root.iter()):
        if el.text and el.text.strip() and clean_text(REG_CLEAN, el.text).strip():
            el.text = translate_text(el.text, translate_fn, verbose=verbose)
        if el.tail and el.tail.strip() and clean_text(REG_CLEAN, el.tail).strip():
            el.tail = translate_text(el.tail, translate_fn, verbose=verbose)

    tree.write(str(path), encoding="utf-8", xml_declaration=True, pretty_print=False)


def translate_html(path: Path, translate_fn: Callable[[str], str], verbose: bool=False):
    parser = etree.HTMLParser(recover=True)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    skip_tags = {"script", "style", "noscript"}

    for el in track(root.iter()):
        tag = el.tag.lower() if isinstance(el.tag, str) else ""
        if tag in skip_tags:
            continue
        if el.text and el.text.strip() and clean_text(REG_CLEAN, el.text).strip():
            el.text = translate_text(el.text, translate_fn, verbose=verbose)
        if el.tail and el.tail.strip() and clean_text(REG_CLEAN, el.tail).strip():
            el.tail = translate_text(el.tail, translate_fn, verbose=verbose)

    html_str = etree.tostring(tree, encoding="unicode", method="html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_str)


