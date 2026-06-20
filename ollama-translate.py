#!/usr/bin/env python3
################################################################################
# @file	    ollama-translate.py
# @date	    Mo Jun 2026
# @author	Dimitri Simon
#
# PROJECT:  ollama-translate
#
# MODIFIED: Mon Jun 15 2026
# BY:		Dimitri Simon
#
# Copyright (c) 2026 Dimitri Simon
#
################################################################################

from lxml import etree
import argparse, zipfile, sys, os, tempfile, shutil, time, datetime, ollama, re, json, csv, html
from rich.progress import track
from pathlib import Path
from time import localtime, strftime
from prompt import PROMPT
from utils import pull_model
from conf import *
from format import *

def eprint(*args):
	print(f"Error:", *args, file=sys.stderr)

if __name__ == '__main__':
	def validation_lang(lang: str, ext: list[str] = []):
		lang = lang.lower()
		if lang in ext:
			return lang
		if lang not in LANG_DICT:
			raise argparse.ArgumentTypeError(f"Language '{lang}' isn't valid")
		return lang

	def show_langs(shorten: bool = True) -> None:
		l = [f"{k} {v}" for k, v in LANG_DICT.items() if not shorten or len(k) == 2]
		txt_langs = ""

		def get_nth(index: int) -> str:
			return l[index] if index < len(l) else ""

		MAX_CELL_WIDTH = len(max(l, key=len)) + 1
		ELEMENTS_ONELINE = (os.get_terminal_size().columns - 1) // MAX_CELL_WIDTH
		if ELEMENTS_ONELINE < 1:
			ELEMENTS_ONELINE = 1
		if ELEMENTS_ONELINE > 8:
			ELEMENTS_ONELINE = 8

		for i in range(0, len(l), ELEMENTS_ONELINE):
			txt_langs += f"{''.join([f'%-{MAX_CELL_WIDTH}s' for _ in range(ELEMENTS_ONELINE)])}\n" % tuple(get_nth(i + j) for j in range(ELEMENTS_ONELINE))
		print(txt_langs)

	LANG_DICT = {}
	with open('lang.json', encoding="utf-8") as json_file:
		LANG_DICT = json.load(json_file)

	parser_langs = argparse.ArgumentParser(add_help=False)
	group_list = parser_langs.add_mutually_exclusive_group()
	group_list.add_argument('-l', '--languages', action='store_const', const=show_langs, dest='list', help="list languages (shorten)")
	group_list.add_argument('-ll', '--languages-full', action='store_const', const=lambda: show_langs(False), dest='list', help="list languages (full)")
	group_list.set_defaults(list=lambda: True)
	args, _unknown = parser_langs.parse_known_args()

	args.list() or sys.exit(0)

	parser = argparse.ArgumentParser(
		usage="{} INPUT_LANG OUTPUT_LANG {{ INPUT_FILE | -t TEXT }}".format(Path(__file__).name),
		description="Translate files using a local Ollama model",
		epilog="Default model: " + f"{LLM_MODEL}:{LLM_MODEL_TAG_DEFAULT}\nSupported file formats: "+", ".join(list(TRANSLATE_DISPATCHER.keys())),
		formatter_class=argparse.RawTextHelpFormatter,
		parents=[parser_langs]
	)
	parser.add_argument('INPUT_LANG', nargs=1, type=lambda l: validation_lang(l, LANGUAGE_AGNOSTIC),
						help='base language in input file.\nUse "-", "all" or "any" to translate from any language everything\nIf a language is specified, any other language will be kept as-is')
	parser.add_argument('OUTPUT_LANG', nargs=1, type=validation_lang, help='target language in output file')
	parser.add_argument('INPUT_FILE', nargs='?', type=lambda x: Path(x).resolve(strict=True), help='file to translate')


	group_parser = parser.add_mutually_exclusive_group()
	group_parser.add_argument('-t', '--text', type=str, help="text to translate")
	group_parser.add_argument('-r', '--recursive', action="store_true", help="translate recursively all supported files in INPUT_FILE")

	parser.add_argument('-o', '--output-file', default=OUTPUT_FILE_DEFAULT, dest="output_file", type=str,
						help='Output basename file translated. Possible formats :\n  {n} basename\n  {l} target language\nDefault: %s' % OUTPUT_FILE_DEFAULT)
	parser.add_argument('--tag', type=str, default=LLM_MODEL_TAG_DEFAULT, help="model's tag")
	parser.add_argument('--prompt', choices=["fast", "balance", "accurate"], type=str, default="accurate", help="type of prompt")
	parser.add_argument('-v', '--verbose', action="store_true", help="show original and translated texts")
	args = parser.parse_args()


	if (args.INPUT_FILE is None) and (args.text is None):
		parser.error("INPUT_FILE or -t/--text required")
	elif (args.INPUT_FILE is not None) and (args.text is not None):
		parser.error("Provide either INPUT_FILE or -t/--text, but not both")

	try:
		pull_model(f"{LLM_MODEL}:{args.tag}")

		# print(args)
		args.INPUT_LANG = args.INPUT_LANG[0]
		args.OUTPUT_LANG = args.OUTPUT_LANG[0]
		# args.INPUT_FILE = args.INPUT_FILE[0]


		prompt_type = "accurate_any" if args.INPUT_LANG in LANGUAGE_AGNOSTIC else args.prompt

		system_prompt = PROMPT[prompt_type].format(
			SOURCE_LANG=LANG_DICT.get(args.INPUT_LANG, args.INPUT_LANG),
			SOURCE_CODE=args.INPUT_LANG,
			TARGET_LANG=LANG_DICT.get(args.OUTPUT_LANG, args.OUTPUT_LANG),
			TARGET_CODE=args.OUTPUT_LANG,
		)

		def translate_full(full_text: str) -> str:
			messages = [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": full_text}
			]
			response = ollama.chat(
				model=f"{LLM_MODEL}:{args.tag}",
				messages=messages
			)
			return response['message']['content'].strip()

		def source_lang() -> str:
			if args.INPUT_LANG in LANGUAGE_AGNOSTIC:
				return "agnostic"
			return f"{LANG_DICT[args.INPUT_LANG]} ({args.INPUT_LANG})"

		if args.text:
			if args.verbose:
				print(f"model:  {LLM_MODEL}:{args.tag}")
				print(f"source: {source_lang()}")
				print(f"target: {LANG_DICT[args.OUTPUT_LANG]} ({args.OUTPUT_LANG})")
				print(f"prompt: {prompt_type}")
				print()
			print(translate_full(args.text))
			sys.exit(0)

		output = args.output_file.format(
			n=args.INPUT_FILE.stem,
			l=args.OUTPUT_LANG
		)
		if args.INPUT_FILE.is_file():
			output += args.INPUT_FILE.suffix.lower()


		if Path(output).exists():
			eprint(f"File '{output}' already exists")
			a = ""
			while a != "y":
				a = input("Do you want to delete this file ? [y/N] ").lower()
				if a == "n":
					sys.exit(0)
			print()

		if args.INPUT_FILE.is_file():
			shutil.copyfile(args.INPUT_FILE, output)

		elif args.INPUT_FILE.is_dir():
			if args.recursive != True:
				raise RuntimeError(f"'{args.INPUT_FILE}' is a directory, pass -r/--recursive if you intended to translate all supported files in this directory")
			shutil.copytree(args.INPUT_FILE, output, dirs_exist_ok=True)

		else:
			raise RuntimeError(f"Unknown type of '{args.INPUT_FILE}'")

	except RuntimeError as e:
		eprint(e)
		sys.exit(1)

	def translate_file(file: Path):
		if TRANSLATE_DISPATCHER.get(file.suffix.lower()):
			TRANSLATE_DISPATCHER[file.suffix.lower()](file, translate_full, args.verbose)

	try:
		if args.verbose:
			print(f"model:  {LLM_MODEL}:{args.tag}")
			print(f"source: {source_lang()}")
			print(f"target: {LANG_DICT[args.OUTPUT_LANG]} ({args.OUTPUT_LANG})")
			print(f"prompt: {prompt_type}")
			print(f"output: {output}")
			# print()

		start_time = time.time()
		print(strftime("time:   %Y-%m-%d %H:%M:%S", localtime()))
		if args.INPUT_FILE.is_file():
			output = Path(output)
			if not TRANSLATE_DISPATCHER.get(output.suffix.lower()):
				raise ValueError(f"Unsupported or unimplemented format: {output.suffix.lower()}")
			translate_file(output)

		else:
			for root, dirs, files in os.walk(output):
				for f in files:
					# print(output+"/"+f, dirs)
					translate_file(Path(output+"/"+f))

	except ValueError as e:
		eprint(e)
	except KeyboardInterrupt:
		pass

	print()
	print(strftime("%Y-%m-%d %H:%M:%S", localtime()))
	print("Elapsed time: ", str(datetime.timedelta(seconds=int(time.time() - start_time))))
