import os
import sys
import os.path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))

from config import FOLDER
from pdf_splitter import PDFParser

def generate_data_files(directory):
    for subdirectory, folders, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[-1] == '.pdf':
                with PDFParser(os.path.sep.join([subdirectory, file])) as parser:
                    parser.generate_data_file()

generate_data_files(FOLDER)
