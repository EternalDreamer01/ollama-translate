
EXCLUDED_WORDS = [
	r"GitHub",
	r"GitLab",
	r"LinkedIn",
	r"Facebook",
	r"Reddit",
	r"Quora",
	r"Twitter",
	r"StackOverflow",
	r"Windows",
	r"Linux",
	r"C\\+\\+",
	r"Rust",
	r"Node.?JS",
	r"NoSQL",
	r"Git",
	r"Docker",
	r"Regex",
	r"VS ?Code",
	r"Kdenlive",
	r"Microsoft",
	r"LibreOffice",
	r"Nmap",
	r"Wireshark"
]

LLM_MODEL = "gemma3"
LLM_MODEL_TAG_DEFAULT = "4b"

NS = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
TEXT_NS = NS['text']
LINE_BREAK_TAG = '{%s}line-break' % TEXT_NS

LANGUAGE_AGNOSTIC = ["-", "all", "any"]
OUTPUT_FILE_DEFAULT = "{n}-{l}.odt"