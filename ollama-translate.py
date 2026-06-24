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

import argparse, sys, os, shutil, time, datetime, ollama, re, json, csv
from pathlib import Path
from time import localtime, strftime
from prompt import PROMPT
from utils import pull_model
from conf import *
from format import *


def main(INPUT_LANG: str, OUTPUT_LANG: str, INPUT_FILE: Path|None=None, OUTPUT_FILE: str|None=None, TEXT: str|None=None, recursive: bool=False, exclude: list[str]=[], tag: str=LLM_MODEL_TAG_DEFAULT, prompt: str="accurate", force_overwrite: bool=False, quiet: bool=False, context_aware: int=0, verbose: bool=False):
	try:
		if (INPUT_FILE is None) and (TEXT is None):
			raise argparse.ArgumentError("INPUT_FILE or -t/--text required")
		elif (INPUT_FILE is not None) and (TEXT is not None):
			raise argparse.ArgumentError("Provide either INPUT_FILE or -t/--text, but not both")
		if INPUT_LANG == OUTPUT_LANG:
			raise argparse.ArgumentError("INPUT_LANG is the same as OUTPUT_LANG")

		pull_model(f"{LLM_MODEL}:{tag}")

		prompt_type = "accurate_any" if INPUT_LANG in LANGUAGE_AGNOSTIC else prompt

		system_prompt = PROMPT[prompt_type].format(
			SOURCE_LANG=LANG_DICT.get(INPUT_LANG, INPUT_LANG),
			SOURCE_CODE=INPUT_LANG,
			TARGET_LANG=LANG_DICT.get(OUTPUT_LANG, OUTPUT_LANG),
			TARGET_CODE=OUTPUT_LANG,
		)

		if exclude:
			REG_CLEAN.insert(0, (r"|".join(map(re.escape, exclude)), re.IGNORECASE))

		history = []
		# verbose = True
		def translate_text(text: str) -> str:
			if not text or not text.strip():
				return text
			cleaned = clean_text(REG_CLEAN, text)
			# print(cleaned)
			if not cleaned:
				return text
			if verbose:
				print(f"\n\x1b[37m{text}\x1b[0m")
			messages = [
				msg
				for i, o in history
				for msg in [
					{"role": "user", "content": i},
					{"role": "assistant", "content": o},
				]
			] + [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": text}
			]
			response = ollama.chat(
				model=f"{LLM_MODEL}:{tag}",
				messages=messages
			)
			out = response['message']['content'].strip()
			if context_aware > 0:
				if len(history) > context_aware:
					history.pop(0)
				history.append((text, out))
			if verbose:
				print(out)
			return out

		def source_lang() -> str:
			if INPUT_LANG in LANGUAGE_AGNOSTIC:
				return "agnostic"
			return f"{LANG_DICT.get(INPUT_LANG, INPUT_LANG)} ({INPUT_LANG})"

		if TEXT:
			if verbose:
				print(f"model:  {LLM_MODEL}:{tag}")
				print(f"source: {source_lang()}")
				print(f"target: {LANG_DICT.get(OUTPUT_LANG, OUTPUT_LANG)} ({OUTPUT_LANG})")
				print(f"prompt: {prompt_type}")
				print()
			return translate_text(TEXT)

		output = OUTPUT_FILE.format(
			n=INPUT_FILE.stem,
			l=OUTPUT_LANG
		) if OUTPUT_FILE != "/dev/null" else "/dev/null"

		# Append extension if not already present
		if INPUT_FILE.is_file() and output != "/dev/null" and Path(output).suffix.lower() != INPUT_FILE.suffix.lower():
			output += INPUT_FILE.suffix.lower()

		if not force_overwrite and Path(output).exists():
			eprint(f"File '{output}' already exists")
			a = ""
			while a != "y":
				a = input("Do you want to delete this file ? [y/N] ").lower()
				if a == "n":
					sys.exit(0)
			print()

		if INPUT_FILE.is_file():
			shutil.copyfile(INPUT_FILE, output)

		elif INPUT_FILE.is_dir():
			if recursive != True:
				raise RuntimeError(f"'{INPUT_FILE}' is a directory, pass -r/--recursive if you intended to translate all supported files in this directory")
			shutil.copytree(INPUT_FILE, output, dirs_exist_ok=True)

		else:
			raise RuntimeError(f"Unknown type of '{INPUT_FILE}'")

	except argparse.ArgumentError as e:
		eprint(e)
		sys.exit(1)
	except RuntimeError as e:
		eprint(e)
		sys.exit(1)

	def translate_file(file: Path) -> str|None:
		if TRANSLATE_DISPATCHER.get(file.suffix.lower()):
			return TRANSLATE_DISPATCHER[file.suffix.lower()](file, translate_text)

	ret = ""
	ki = False
	try:
		if verbose:
			print(f"model:  {LLM_MODEL}:{tag}")
			print(f"source: {source_lang()}")
			print(f"target: {LANG_DICT.get(OUTPUT_LANG, OUTPUT_LANG)} ({OUTPUT_LANG})")
			print(f"prompt: {prompt_type}")
			print(f"output: {output}")
			# print()

		start_time = time.time()
		if not quiet:
			print(strftime("time:   %Y-%m-%d %H:%M:%S", localtime()))
		# print(output)
		if INPUT_FILE.is_file():
			output = Path(output)
			if not TRANSLATE_DISPATCHER.get(INPUT_FILE.suffix.lower()):
				raise ValueError(f"Unsupported or unimplemented format: {INPUT_FILE.suffix.lower()}")
			ret = translate_file(output)

		else:
			for root, dirs, files in os.walk(output):
				for f in files:
					# print(output+"/"+f, dirs)
					ret += translate_file(Path(output+"/"+f))
					ret += "\v"

	except ValueError as e:
		eprint(e)
	except KeyboardInterrupt:
		ki = True

	if not quiet:
		print()
		print(strftime("%Y-%m-%d %H:%M:%S", localtime()))
		print("Elapsed time:", str(datetime.timedelta(seconds=int(time.time() - start_time))))

	if ki:
		raise KeyboardInterrupt

	return (ret or "").strip()

if __name__ == '__main__':
	parser_langs = argparse.ArgumentParser(add_help=False)
	group_list = parser_langs.add_mutually_exclusive_group()
	group_list.add_argument('-l', '--languages', action='store_const', const=show_langs, dest='list', help="list languages (shorten)")
	group_list.add_argument('-ll', '--languages-full', action='store_const', const=lambda: show_langs(False), dest='list', help="list languages (full)")
	group_list.set_defaults(list=lambda:True)
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
	group_parser.add_argument('-t', '--text', type=str, dest="TEXT", help="text to translate")
	group_parser.add_argument('-r', '--recursive', action="store_true", help="translate recursively all supported files in INPUT_FILE")

	parser.add_argument('-o', '--output-file', default=OUTPUT_FILE_DEFAULT, metavar="FILE", dest="OUTPUT_FILE", type=str,
						help='Output basename file translated. Possible formats :\n  {n} basename\n  {l} target language\nDefault: %s' % OUTPUT_FILE_DEFAULT)
	parser.add_argument('-e', '--exclude', metavar="WORDS", type=lambda s: [t.strip() for t in s.split(',')], help="Comma-separated list of words to filter out")
	parser.add_argument('--tag', type=str, default=LLM_MODEL_TAG_DEFAULT, help="model's tag")
	parser.add_argument('--context-aware', metavar="LENGTH", type=int, default=0, help="Context aware can increase translation accuracy")
	parser.add_argument('--prompt', choices=["fast", "balance", "accurate"], type=str, default="accurate", help="type of prompt")
	parser.add_argument('-v', '--verbose', action="store_true", help="show original and translated texts")
	args = parser.parse_args()

	# print(args.__dict__)

	args.INPUT_LANG = args.INPUT_LANG[0]
	args.OUTPUT_LANG = args.OUTPUT_LANG[0]
	del args.list

	try:
		text = main(**args.__dict__)
		if args.TEXT is not None and text:
			print(text)
	except KeyboardInterrupt:
		pass
