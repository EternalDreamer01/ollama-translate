
from .office import *
from .plaintext import *

TRANSLATE_DISPATCHER = {
	".odt": translate_odt,
	".ods": translate_ods,
	".odp": translate_odp,
	".docx": translate_docx,
	".xlsx": translate_xlsx,
	".pptx": translate_pptx,
	".txt": translate_txt,
	".csv": translate_csv,
	".xml": translate_xml,
	".html": translate_html,
	".md": translate_md,
	".latex": translate_latex,
	# ".pdf": translate_pdf,
}