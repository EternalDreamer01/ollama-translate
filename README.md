# Ollama Translate

Translate documents using a local Ollama model.

This tool extracts text from supported files, sends it to a local LLM for translation, and writes the translated content back to a new file.

## Features

- Local translation with Ollama
- Supports multiple file formats: `.odt`, `.ods`, `.odp`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.csv`, `.xml`, `.html`, `.htm`, `.md`, `.tex`
- Preserves structure
- Verbose mode to show original and translated text
- Language selection for source and target, or agnostic source language

<!-- ### PDF
- `.pdf` is supported in a limited way:
  - text is extracted page by page
  - translated text is written into a new PDF
  - original layout is not preserved -->

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/download)

## Python dependencies

```sh
pip3 install -r requirements.txt
```

## Usage

```sh
./ollama-translate.py INPUT_LANG OUTPUT_LANG { INPUT_FILE | -t TEXT }
```

__Examples:__
```sh
./ot.py en es document.docx	# Translate file from English to Spanish
./ot.py - es document.docx	# Translate file from any language to Spanish
./ot.py -r en es dir/		# Translate files recursively from English to Spanish

./ot.py en es -t "Hello world !" # Translate text from English to Spanish
```

List available languages:
```sh
./ot.py -l	# Short
./ot.py -ll	# Full
```
