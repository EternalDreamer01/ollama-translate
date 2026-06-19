import ollama
from lxml import etree
import re
from conf import *
from typing import Callable

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


def clean_text(rgx_list, text: str):
    new_text = text
    for rgx_match in rgx_list:
        if isinstance(rgx_match, str):
            new_text = re.sub(rgx_match, '', new_text)
        else:
            new_text = re.sub(rgx_match[0], '', new_text, flags=rgx_match[1])
    return new_text



def translate_text(text: str, translate_fn: Callable[[str], str], verbose=False):
    if not text or not text.strip():
        return text
    cleaned = clean_text(REG_CLEAN, text)
    if not cleaned.strip():
        return text
    if verbose:
        print(f"\n\x1b[37m{text}\x1b[0m")
    out = translate_fn(text)
    if verbose:
        print(out)
    return out
