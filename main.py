#!/usr/bin/python3
################################################################################
# @file      main.py
# @brief     
# @date      Mo Jun 2026
# @author    Dimitri Simon
# 
# PROJECT:   ollama-translator
# 
# MODIFIED:  Mon Jun 15 2026
# BY:        Dimitri Simon
# 
# Copyright (c) 2026 Dimitri Simon
# 
################################################################################

from lxml import etree
import zipfile
import sys

NS = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}

def replace_paragraph_by_index(path, idx, new_text):
    with zipfile.ZipFile(path, 'r') as z:
        content = z.read('content.xml')
        others = {n: z.read(n) for n in z.namelist() if n != 'content.xml'}
    root = etree.fromstring(content)
    paras = root.findall('.//text:p', NS) + root.findall('.//text:h', NS)
    if idx < 0 or idx >= len(paras):
        raise IndexError('paragraph index out of range')
    p = paras[idx]
    # remove all children, set text (keeps tag and attributes)
    for c in list(p):
        p.remove(c)
    p.text = new_text
    new_content = etree.tostring(root, xml_declaration=True, encoding='UTF-8')
    # write back same as above (create temp zip and move)
    # ... (reuse writing code from first function)


def odt_paragraphs(path):
    with zipfile.ZipFile(path) as z:
        content = z.read('content.xml')
    root = etree.fromstring(content)

    def paragraph_text(el):
        parts = []
        for node in el.iter():
            # element text
            if node.text:
                parts.append(node.text)
            # explicit ODf line-break element -> newline
            if node.tag == '{%s}line-break' % NS['text']:
                parts.append('\n')
            # tail text (text after this node)
            if node.tail:
                parts.append(node.tail)
        return ''.join(parts)

    # collect paragraphs and headings
    paras = []
    for tag in ('text:p', 'text:h'):
        for p in root.findall('.//'+tag, NS):
            paras.append(paragraph_text(p))
    return paras

paras = odt_paragraphs(sys.argv[1])
text = '\n'.join(p.strip() for p in paras if p.strip())  # join paragraphs with blank line
print(text)

# print(doc.content) #.get_sheet(0)


# print(f"Value of A1: {sheet.get_cell('A1').value}")
# sheet.set_value('B2', 'Updated Value')

# doc.save('modified_spreadsheet.ods')