import re

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

REG_CLEAN = [
    r"[\w_\-\.]+@([\w\-]+\.)+[\w\-]{2,}",					# email
    r"(https://[^ ]{3,}|[^ ]+\.com\/?[^ ]*)",				# url/domain
    (r"[$&+,:;=?@#|'<>.^*()%!\-\u2013\u2014]", re.UNICODE),	# special character
    r"[\d \+]{4,}",											# phone number
    r"[A-Z0-9]{3,}",										# capital name
    r"\d+",													# number
    (r"\b(" + r'|'.join(EXCLUDED_WORDS) + r")\b", re.IGNORECASE)
]

LLM_MODEL = "gemma3"
LLM_MODEL_TAG_DEFAULT = "4b"

NS = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
TEXT_NS = NS['text']
LINE_BREAK_TAG = '{%s}line-break' % TEXT_NS

LANGUAGE_AGNOSTIC = ["-", "all", "any"]
OUTPUT_FILE_DEFAULT = "{n}-{l}"