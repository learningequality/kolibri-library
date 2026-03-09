import os
import sys
import os.path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))

from config import FOLDER
from pdf_splitter import PDFParser

def generate_indices(directory):
    for subdirectory, folders, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[-1] == '.pdf':
                filepath = os.path.sep.join([subdirectory, file])
                with PDFParser(filepath) as parser:
                    parser.generate_index_file('.')


generate_indices(FOLDER)
