import ollama
from lxml import etree
import re, json
from conf import *
from typing import Callable
from os import get_terminal_size
from sys import stderr
from argparse import ArgumentTypeError

def pull_model(model: str):
	try:
		ollama.show(model)
	except ollama.ResponseError:
		try:
			import sys
			from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

			current_digest = ""
			tasks = {}

			with Progress(
				TextColumn("[bold blue]{task.description}"),
				BarColumn(),
				DownloadColumn(),
				TransferSpeedColumn(),
				TimeRemainingColumn(),
			) as progress:
				for item in ollama.pull(model, stream=True):
					digest = item.get("digest", "")

					if digest != current_digest and current_digest in tasks:
						progress.stop_task(tasks[current_digest])

					if not digest:
						print(item.get("status"))
						continue

					if digest not in tasks and (total := item.get("total")):
						tasks[digest] = progress.add_task(
							f"pulling {digest[7:19]}",
							total=total,
						)

					if completed := item.get("completed"):
						progress.update(tasks[digest], completed=completed)

					current_digest = digest

		except KeyboardInterrupt:
			sys.exit(0)


def set_mixed_text(el, text):
    """
    Replace element contents with text, converting newlines to <text:line-break/>
    and preserving element tag/attributes.
    """
    for c in list(el):
        el.remove(c)

    if text is None:
        el.text = None
        return

    parts = text.split('\n')
    el.text = parts[0] if parts else None
    for part in parts[1:]:
        lb = etree.Element(LINE_BREAK_TAG, nsmap={})
        el.append(lb)
        if part:
            lb.tail = part


def paragraph_text(el):
    parts = []
    for node in el.iter():
        if node.text:
            parts.append(node.text)
        if node.tag == LINE_BREAK_TAG:
            parts.append('\n')
        if node.tail:
            parts.append(node.tail)
    return ''.join(parts)


def clean_text(rgx_list: list, text: str):
    new_text = text
    for rgx_match in rgx_list:
        if isinstance(rgx_match, str):
            new_text = re.sub(rgx_match, '', new_text)
        else:
            new_text = re.sub(rgx_match[0], '', new_text, flags=rgx_match[1])
    return new_text.strip()

LANG_DICT = {}
with open('lang.json', encoding="utf-8") as json_file:
	LANG_DICT = json.load(json_file)

def validation_lang(lang: str, ext: list[str] = []) -> str:
	lang = lang.lower()
	if lang in ext:
		return lang
	if lang not in LANG_DICT:
		raise ArgumentTypeError(f"Language '{lang}' isn't valid")
	return lang

def show_langs(shorten: bool = True) -> None:
	l = [f"{k} {v}" for k, v in LANG_DICT.items() if not shorten or len(k) == 2]
	txt_langs = ""

	def get_nth(index: int) -> str:
		return l[index] if index < len(l) else ""

	MAX_CELL_WIDTH = len(max(l, key=len)) + 1
	ELEMENTS_ONELINE = (get_terminal_size().columns - 1) // MAX_CELL_WIDTH
	if ELEMENTS_ONELINE < 1:
		ELEMENTS_ONELINE = 1
	if ELEMENTS_ONELINE > 8:
		ELEMENTS_ONELINE = 8

	for i in range(0, len(l), ELEMENTS_ONELINE):
		txt_langs += f"{''.join([f'%-{MAX_CELL_WIDTH}s' for _ in range(ELEMENTS_ONELINE)])}\n" % tuple(get_nth(i + j) for j in range(ELEMENTS_ONELINE))
	print(txt_langs)

def eprint(*args):
	print(f"Error:", *args, file=stderr)

def file_read(path: str) -> str:
	with open(path, "r", encoding="utf-8", errors="ignore") as f:
		return f.read()

def file_readlines(path: str) -> list[str]:
	with open(path, "r", encoding="utf-8", errors="ignore") as f:
		return f.readlines()

def file_write(path: str, text: str) -> str:
	with open(path, "w", encoding="utf-8") as f:
		f.write(text)
	return text

def file_writelines(path: str, text: list[str]) -> str:
	with open(path, "w", encoding="utf-8", newline="") as f:
		f.writelines(text)
	return "".join(text)