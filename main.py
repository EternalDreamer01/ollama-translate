#!/usr/bin/python3
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
import argparse, zipfile, sys, os, colorama, tempfile, shutil, time, datetime, ollama, re
from lang import lang_dict
from rich.progress import track
from pathlib import Path
from time import localtime, strftime
from prompt import PROMPT
from colorama import Fore, Style

LLM_MODEL = "translategemma"
LLM_MODEL_PARAMETERS_DEFAULT = 4

NS = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
TEXT_NS = NS['text']
LINE_BREAK_TAG = '{%s}line-break' % TEXT_NS

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
	reg_text = re.compile(r"^([a-z]|[\d \+]+|[\w\-\.]+@([\w-]+\.)+[\w-]{2,}|(GitHub|LinkedIn):?\s*https?:\/\/[-a-zA-Z0-9@%._\+~#=]{1,256}\.[a-z]{2,128}\b[-a-zA-Z0-9@:%_\+.~#?&\/\/=]*)$")

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

	def clean_text(rgx_list, text):
		new_text = text
		for rgx_match in rgx_list:
			new_text = re.sub(rgx_match, '', new_text, flags=re.UNICODE)
		return new_text

	regex_clean = [
		r"[\w_\-\.]+@([\w\-]+\.)+[\w\-]{2,}",	# email
		r"(https://[^ ]{3,}|[^ ]+\.com\/?[^ ]*)", # url
		r"[$&+,:;=?@#|'<>.^*()%!\-\u2013\u2014]",			# special character
		r"[\d \+]+",							# number
		r"[A-Z]{3,}",							# name in capital
		r"(GitHub|GitLab|LinkedIn|Facebook|Reddit|Quora|StackOverflow)" # sites
	]

	# apply transformation to each paragraph element in-place
	for p in track(paras):
		orig = paragraph_text(p).strip()
		if orig and clean_text(regex_clean, orig).strip():
			print(f"\n\x1b[37m{orig}\x1b[0m")
			new = transform_fn(orig)
			print(new)
			# ensure string
			if new is None:
				new = ''
			_set_mixed_text(p, str(new))

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
	def validation_lang(lang: str):
		if not lang in lang_dict:
			raise argparse.ArgumentTypeError(f"Language '{lang}' isn't valid")
		return lang

	def show_langs(shorten: bool=True) -> str:
		l = [f"{k} ({v})" for k, v in lang_dict.items() if not shorten or len(k) == 2]
		txt_langs = ""
		def get_nth(index: int) -> str:
			return l[index] if index < len(l) else ""

		ELEMENTS_ONELINE = 5
		# print(' '.join(['%-18s' for _ in range(ELEMENTS_ONELINE)]))
		# print(tuple(get_nth(j) for j in range(ELEMENTS_ONELINE)))

		for i in range(0, len(l), ELEMENTS_ONELINE):
			txt_langs += f"  {' '.join(['%-18s' for _ in range(ELEMENTS_ONELINE)])}\n" % tuple(get_nth(i+j) for j in range(ELEMENTS_ONELINE))
		return txt_langs

	parser = argparse.ArgumentParser(
		description="Translate LibreOffice file using a local Ollama model",
		epilog="Default model: "+f"{LLM_MODEL}:{LLM_MODEL_PARAMETERS_DEFAULT}b",
		# formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument('output_lang', nargs=1, type=validation_lang, help='target language')
	parser.add_argument('input_file', nargs=1, type=lambda x: Path(x).resolve(strict=True), help='file to translate')
	group_input_language = parser.add_mutually_exclusive_group()
	group_input_language.add_argument('-i', '--input-lang', dest='input_lang', type=validation_lang, help='The base language to translate from')
	group_input_language.add_argument('-a', '--agnostic', action="store_true", help="language agnostic translate (default)")

	parser.add_argument('-o', '--output-file', default="out.odt", dest="output_file", type=str, help='The output file translated')
	parser.add_argument('-p', '--parameters', choices=[4, 12, 27], type=int, default=LLM_MODEL_PARAMETERS_DEFAULT, help="size of model's parameters (billion)")
	parser.add_argument('--prompt', choices=["fast", "balance", "accurate"], type=str, default="fast", help="type of prompt")
	parser.add_argument('-l', '--languages', action="store_true", help="list languages (shorten)")
	parser.add_argument('-ll', '--languages-full', action="store_true", help="list languages (full)")
	args = parser.parse_args()

	# print(args)
	if args.languages:
		print(show_langs())
		sys.exit(0)
	elif args.languages_full:
		print(show_langs(False))
		sys.exit(0)

	params = args.parameters
	try:
		ollama.show(f"{LLM_MODEL}:{params}b")
	except ollama.ResponseError:
		ollama.pull(f"{LLM_MODEL}:{params}b")

	args.output_lang = args.output_lang[0]
	args.input_file = args.input_file[0]
	# print(args)

	prompt = PROMPT["accurate_any" if args.agnostic or not args.input_lang else args.prompt]

	def translate_full(full_text: str) -> str:
		system_prompt = PROMPT["accurate_any" if args.agnostic else args.prompt] \
		.format(
			SOURCE_LANG=lang_dict.get(args.input_lang, args.input_lang),
			SOURCE_CODE=args.input_lang,
			TARGET_LANG=lang_dict.get(args.output_lang, args.output_lang),
			TARGET_CODE=args.output_lang,
			TEXT=full_text
		)
		
		messages = [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": full_text}
		]

		# start_time = time.time()

		response = ollama.chat(
			model=f"{LLM_MODEL}:{params}b",
			messages=messages
		)
		# elapsed_time = time.time() - start_time
		return response['message']['content']

	# Apply transform in-place
	start_time = time.time()
	try:
		print(strftime("%Y-%m-%d %H:%M:%S", localtime()))
		edit_paragraphs_inplace(args.input_file, translate_full)

		# Print joined non-empty paragraphs (same behavior as original)
		paras = odt_paragraphs(args.input_file)
		text = '\n'.join(p.strip() for p in paras if p.strip())
		print(text)
	except KeyboardInterrupt:
		pass

	print()
	print(strftime("%Y-%m-%d %H:%M:%S", localtime()))
	print("Elapsed time: ", str(datetime.timedelta(seconds=int(time.time() - start_time))))
