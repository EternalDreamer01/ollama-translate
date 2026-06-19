#!/usr/bin/env python3
################################################################################
# @file	  main.py
# @brief	 Edit all ODT paragraphs in-place by applying a transform function
# @date	  Mo Jun 2026
# @author	Dimitri Simon
#
# PROJECT:   ollama-translate
#
# MODIFIED:  Mon Jun 15 2026
# BY:		Dimitri Simon
#
# Copyright (c) 2026 Dimitri Simon
#
################################################################################

from lxml import etree
import argparse, zipfile, sys, os, tempfile, shutil, time, datetime, ollama, re, json
from rich.progress import track
from pathlib import Path
from time import localtime, strftime
from prompt import PROMPT
from utils import pull_model
from conf import *
# import reformat

def _set_mixed_text(el, text):
	"""
	Replace element contents with text, converting newlines to <text:line-break/>
	and preserving element tag/attributes.
	"""
	# remove existing children
	for c in list(el):
		el.remove(c)
	if not text:
		el.text = None
		return
	parts = text.split('\n')
	el.text = parts[0] if parts else None
	for part in parts[1:]:
		lb = etree.Element(LINE_BREAK_TAG, nsmap={})
		el.append(lb)
		# text after the line-break
		if part:
			# set tail on line-break element for the following text
			lb.tail = part

def edit_paragraphs_inplace(path, transform_fn):
	"""
	Open ODT/ODP (zip) at `path`, apply transform_fn(original_text) to every
	paragraph (<text:p>) and heading (<text:h>), and write changes back
	in-place (atomic replace).
	transform_fn: callable that accepts a single string and returns a string.
	"""
	# read archive contents
	with zipfile.ZipFile(path, 'r') as z:
		names = z.namelist()
		if 'content.xml' not in names:
			raise ValueError('content.xml not found in archive')
		content = z.read('content.xml')
		other_files = {name: z.read(name) for name in names if name != 'content.xml'}

	# parse XML
	root = etree.fromstring(content)

	# find paragraphs and headings (elements themselves)
	paras = root.findall('.//text:p', NS) + root.findall('.//text:h', NS)

	# helper to extract inner text similarly to odt_paragraphs
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

	def clean_text(rgx_list: list[str] | list[tuple[str,re.RegexFlag]], text: str):
		new_text = text
		for rgx_match in rgx_list:
			if isinstance(rgx_match, str):
				new_text = re.sub(rgx_match, '', new_text)
			else:
				new_text = re.sub(rgx_match[0], '', new_text, flags=rgx_match[1])
		return new_text

	regex_clean = [
		r"[\w_\-\.]+@([\w\-]+\.)+[\w\-]{2,}",						# email
		r"(https://[^ ]{3,}|[^ ]+\.com\/?[^ ]*)",					# url
		(r"[$&+,:;=?@#|'<>.^*()%!\-\u2013\u2014]", re.UNICODE),		# special character
		r"[\d \+]+",												# number
		r"[A-Z]{3,}",												# name in capital
		(r"\b("+ r'|'.join(EXCLUDED_WORDS) + r")\b", re.IGNORECASE) # sites
	]

	# apply transformation to each paragraph element in-place
	for p in track(paras):
		orig = paragraph_text(p).strip()
		if orig and clean_text(regex_clean, orig).strip():
			_set_mixed_text(p, transform_fn(orig))

	# serialize modified content.xml
	new_content = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=False)

	# write to a temporary zip then replace original (atomic where possible)
	tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
	os.close(tmp_fd)
	try:
		with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
			# write modified content.xml first (preserve name)
			z.writestr('content.xml', new_content)
			# write back other files preserving original names
			for name, data in other_files.items():
				z.writestr(name, data)
		# replace original file
		shutil.move(tmp_path, path)
	finally:
		if os.path.exists(tmp_path):
			os.remove(tmp_path)

def odt_paragraphs(path):
	with zipfile.ZipFile(path) as z:
		content = z.read('content.xml')
	root = etree.fromstring(content)

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

	paras = []
	for tag in ('text:p', 'text:h'):
		for p in root.findall('.//'+tag, NS):
			paras.append(paragraph_text(p))
	return paras


if __name__ == '__main__':
	def validation_lang(lang: str, ext: list[str] = []):
		lang = lang.lower()
		if lang in ext:
			return lang
		if not lang in LANG_DICT:
			raise argparse.ArgumentTypeError(f"Language '{lang}' isn't valid")
		return lang

	def show_langs(shorten: bool=True) -> None:
		l = [f"{k} {v}" for k, v in LANG_DICT.items() if not shorten or len(k) == 2]
		txt_langs = ""
		def get_nth(index: int) -> str:
			return l[index] if index < len(l) else ""

		MAX_CELL_WIDTH = len(max(l, key=len)) + 1
		# print(max_cell_width)
		ELEMENTS_ONELINE = (os.get_terminal_size().columns - 1) // MAX_CELL_WIDTH
		if ELEMENTS_ONELINE < 1:
			ELEMENTS_ONELINE = 1
		if ELEMENTS_ONELINE > 8:
			ELEMENTS_ONELINE = 8
		# print(' '.join(['%-18s' for _ in range(ELEMENTS_ONELINE)]))
		# print(tuple(get_nth(j) for j in range(ELEMENTS_ONELINE)))

		# print("/".join([k for k in LANGUAGE_AGNOSTIC])+": language agnostic input")
		for i in range(0, len(l), ELEMENTS_ONELINE):
			txt_langs += f"{''.join([f'%-{MAX_CELL_WIDTH}s' for _ in range(ELEMENTS_ONELINE)])}\n" % tuple(get_nth(i+j) for j in range(ELEMENTS_ONELINE))
		print(txt_langs)

	LANG_DICT = {}
	with open('lang.json') as json_file:
		LANG_DICT = json.load(json_file)

	parser_langs = argparse.ArgumentParser(add_help=False)
	group_list = parser_langs.add_mutually_exclusive_group()
	group_list.add_argument('-l', '--languages', action='store_const', const=show_langs, dest='list', help="list languages (shorten)")
	group_list.add_argument('-ll', '--languages-full', action='store_const', const=lambda: show_langs(False), dest='list', help="list languages (full)")
	group_list.set_defaults(list=lambda:True)
	args, _unknown = parser_langs.parse_known_args()

	args.list() or sys.exit(0)

	parser = argparse.ArgumentParser(
		usage="{} input_lang output_lang input_file".format(Path(__file__).name),
		description="Translate files using a local Ollama model",
		epilog="Default model: "+f"{LLM_MODEL}:{LLM_MODEL_TAG_DEFAULT}",
		formatter_class=argparse.RawTextHelpFormatter,
		parents=[parser_langs]
	)
	parser.add_argument('input_lang', nargs=1, type=lambda l: validation_lang(l, LANGUAGE_AGNOSTIC), help='base language in input file.\nUse "-", "all" or "any" to translate from any language everything\nIf a language is specified, any other language will be kept as-is')
	parser.add_argument('output_lang', nargs=1, type=validation_lang, help='target language in output file')
	parser.add_argument('input_file', nargs=1, type=lambda x: Path(x).resolve(strict=True), help='file to translate')
	# group_input_language = parser.add_mutually_exclusive_group(required=True)
	# group_input_language.add_argument('-i', '--input-lang', dest='input_lang', type=validation_lang, help='The base language to translate from')
	# group_input_language.add_argument('-a', '--agnostic', action="store_true", help="language agnostic translate (default)")

	parser.add_argument('-o', '--output-file', default=OUTPUT_FILE_DEFAULT, dest="output_file", type=str, help='Output file translated. Possible formats :\n  {n} basename\n  {l} target language\nDefault: %s' % OUTPUT_FILE_DEFAULT)
	parser.add_argument('-t', '--tag', type=str, default=LLM_MODEL_TAG_DEFAULT, help="model's tag")
	parser.add_argument('--prompt', choices=["fast", "balance", "accurate"], type=str, default="accurate", help="type of prompt")
	# parser.add_argument('-r', '--recursive')
	parser.add_argument('-v', '--verbose', action="store_true", help="show original and translated texts")
	args = parser.parse_args()

	pull_model(f"{LLM_MODEL}:{args.tag}")

	args.input_lang = args.input_lang[0]
	args.output_lang = args.output_lang[0]
	args.input_file = args.input_file[0]


	output = args.output_file.format(
		n=args.input_file.stem,
		l=args.output_lang
	)

	if Path(output).exists():
		print(f"Error: File '{output}' already exists", file=sys.stderr)
		a = ""
		while a != "y":
			a = input("Do you want to delete this file ? [y/N] ").lower()
			if a == "n":
				sys.exit(0)
		# sys.exit(1)

	shutil.copyfile(args.input_file, output)

	prompt_type = "accurate_any" if args.input_lang in LANGUAGE_AGNOSTIC else args.prompt

	print(f"model:  {LLM_MODEL}:{args.tag}")
	print(f"target: {LANG_DICT[args.output_lang]} ({args.output_lang})")
	print(f"output: {output}")
	print(f"prompt: {prompt_type}")
	# shutil.copy(src, dst)
	# sys.exit(0)

	system_prompt = PROMPT[prompt_type] \
		.format(
			SOURCE_LANG=LANG_DICT.get(args.input_lang, args.input_lang),
			SOURCE_CODE=args.input_lang,
			TARGET_LANG=LANG_DICT.get(args.output_lang, args.output_lang),
			TARGET_CODE=args.output_lang,
		)

	def translate_full(full_text: str) -> str:
		messages = [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": full_text}
		]

		# start_time = time.time()

		if args.verbose:
			print(f"\n\x1b[37m{full_text}\x1b[0m")
		response = ollama.chat(
			model=f"{LLM_MODEL}:{args.tag}",
			messages=messages
		)
		if args.verbose:
			print(response['message']['content'].strip())
		# elapsed_time = time.time() - start_time
		return response['message']['content'].strip()

	# Apply transform in-place
	start_time = time.time()
	try:
		print(strftime("time:   %Y-%m-%d %H:%M:%S", localtime()))
		edit_paragraphs_inplace(output, translate_full)

		# Print joined non-empty paragraphs (same behavior as original)
		# paras = odt_paragraphs(args.input_file)
		# text = '\n'.join(p.strip() for p in paras if p.strip())
		# print(text)
	except KeyboardInterrupt:
		pass

	print()
	print(strftime("%Y-%m-%d %H:%M:%S", localtime()))
	print("Elapsed time: ", str(datetime.timedelta(seconds=int(time.time() - start_time))))
