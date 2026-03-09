from io import BytesIO
import itertools
import json
import os
import re
import tempfile

from config import DOWNLOAD_DIRECTORY
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import Destination, NullObject
from PyPDF2.utils import PdfReadError
from ricecooker.config import LOGGER
from ricecooker.utils.downloader import read
from ricecooker.classes import nodes
from tika import parser

# Monkeypatched PyPDF2.PdfFileReader
class CustomDestination(Destination):
    def __init__(self, title, page, typ, *args):
        try:
            super(CustomDestination, self).__init__(title, page, typ, *args)
        except PdfReadError:
            pass

class CustomPDFReader(PdfFileReader):
    def _buildDestination(self, title, array):
        page, typ = array[0:2]
        array = array[2:]
        return CustomDestination(title, page, typ, *array)


class Chapter(object):
    """
        The Chapter object is a class to help with
        representing the pdf index structure with its
        sections and sub-chapters
    """
    offset = None
    def __init__(self, text, start=None):
        self.text = text.strip()
        self.children = []
        self.start = start

    def to_dict(self):
        if self.start:
            return {self.text: self.start}

        chapter_data = {}
        for child in self.children:
            chapter_data.update(child.to_dict())

        if self.offset:
            return {
                'offset': self.offset,
                'chapters': chapter_data
            }

        return {
            self.text: chapter_data
        }

    def add_child(self, text, start=None):
        # Chapters at the same level must have a unique name or they will write to the same key
        if any(c for c in self.children if c.text == text):
            text = "{} ({})".format(text, len([c for c in self.children if c.text == text]))

        chapter = Chapter(text, start=start)

        self.children.append(chapter)
        return chapter


class PDFParser(object):
    # Path to download split pdfs to
    path = None

    # String to remove from index return result
    strings_to_ignore = [
        'Índice',
        'Indice',
        'índice',
        'Guía para maestros -',
    ]

    def __init__(self, url_or_path, directory=DOWNLOAD_DIRECTORY):
        self.directory = directory          # Store split pdfs here
        self.download_url = url_or_path     # Where to read pdf from

        filename, _ = os.path.splitext(os.path.basename(url_or_path))

        # Path to -index.json file
        self.index_path = os.path.sep.join([os.path.dirname(url_or_path), '{}-index.json'.format(filename)])

        # Path to -data.json file
        self.pdf_data_path = os.path.sep.join([os.path.dirname(url_or_path), '{}-data.json'.format(filename)])

    def __enter__(self):
        """ Called when opening context (e.g. with HTMLWriter() as writer: ) """
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        """ Called when closing context """
        self.close()


    def open(self):
        """ Opens pdf file to read from
            Args: None
            Returns: None
        """
        filename = os.path.basename(self.download_url)
        folder, _ext = os.path.splitext(filename)
        self.path = os.path.sep.join([self.directory, folder, filename])
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))

        self.file = open(self.download_url, 'rb')
        self.pdf = CustomPDFReader(self.file)

    def close(self):
        """ Closes main pdf file when done
            Args: None
            Returns: None
        """
        self.file.close() # Make sure zipfile closes no matter what


    def get_page_text(self, index):
        """
            Reads the page text
            Args: index (int) page number to read
            Returns str page text

            ---

            Note: pypdf2 doesn't read all of the text on the page, so
            we need to use tika to read the text for us. However,
            tika will read the full pdf, rather than a single page.
            In order to workaround this, we'll generate a page in memory and
            have tika read from that.

            More on issue here:
            https://stackoverflow.com/questions/35090948/pypdf2-wont-extract-all-text-from-pdf
            (Also avoiding pdftotext as it requires poppler installation)
        """
        tmppdf = BytesIO()
        writer = PdfFileWriter()
        writer.addPage(self.pdf.getPage(index))
        writer.write(tmppdf)
        tmppdf.seek(0)
        return parser.from_buffer(tmppdf)['content']

    def get_data_file(self):
        """
            Reads and returns the -data.json file data
            Args: None
            Returns dict of pdf data

            ---

            Sample pdf data:
              {
                "header": "Section Name",
                "chapters": [
                  {
                    "chapter": "Chapter 1",
                    "path": "path/to/splitfile.pdf",
                    "exercises": [
                      {
                        "description": "Some description",
                        "questions": [
                          {
                            "question": "An apple is a fruit?",
                            "type": "multiple_selection",
                            "answers": {
                              "Yes": true,
                              "No": false
                            }
                          }
                        ]
                      }
                    ]
                  }
                ]
              }
        """
        # Throw an error if there isn't a -data.json file
        if not os.path.exists(self.pdf_data_path):
            raise OSError('Unable to find data file for {}. Please run scripts/generatedata.py command and try again.'.format(self.download_url))

        # Try reading the -data.json file
        with open(self.pdf_data_path, 'rb') as fobj:
            try:
                return json.loads(fobj.read())
            except Exception as e:
                raise OSError('{} is invalid ({}).\n\nPlease edit file and try again'.format(self.pdf_data_path, str(e)))


    # -index.json file generation code
    #######################################################################################################
    def is_valid_chapter(self, text):
        """
            Validates a chapter name (i.e. chapter name is not blank and strings_to_ignore texts are not found)
            Args: text (str) chapter name to validate
            Returns boolean indicating if chapter name is valid
        """
        return text.strip() and not any(t for t in self.strings_to_ignore if t in text)

    def get_index_range(self, index_delimiter):
        current_page = None
        index_start = 0

        # Find the index page by searching for a series of delimiters
        # (using multiple in case the character is common)
        index_str = index_delimiter * 5
        for index in range(0, 20):  # Index is generally within the first 10 pages
            current_page = self.get_page_text(index)
            if current_page and index_str in current_page.replace(' ', ''):
                break
        index_start = index

        # Unable to find index, so return -1 for starting point
        if not current_page:
            return -1, self.pdf.numPages

        # Figure out where the index ends by determining where the
        # delimiter stops appearing
        while index_str in current_page.replace(' ', ''):
            index += 1
            current_page = self.get_page_text(index)

        return index_start, index

    def generate_index_file(self, index_delimiter):
        """
            Generates the -index.json file
            Args: index_delimiter (str) character that is used to separate chapter names
                and page numbers in the pdf
            Returns: str path to -index.json file

            ---

            Sample -index.json data:
                {
                    "offset": 2,
                    "chapters": {
                        "Section Name": {
                            "Chapter 1": 5,
                            "Chapter 2": 10
                        },
                        "Appendix": 15
                    }
                }
        """
        # Don't overwrite the file if it already exists
        if os.path.exists(self.index_path):
            print('-- Found index at {}'.format(self.index_path))
            return self.index_path

        root_chapter = Chapter(self.download_url)
        current_page = None

        index_start, index_end = self.get_index_range(index_delimiter)
        root_chapter.offset = index_end

        # Return None if the index wasn't found
        if index_start == -1:
            return None

        # Read through all index pages and extract chapter information
        current_section = None
        for pagenum in range(index_start, index_end):
            current_page = self.get_page_text(pagenum)
            chapters = [c for c in current_page.split('\n') if self.is_valid_chapter(c)]

            # When there are columns in the index, the page numbers sometimes end up on
            # separate lines. Use this to help unify the chapters
            page_number_index = 0
            page_numbers = sorted([int(num) for num in chapters if num.isdigit()])

            # Read chapters in the list of chapters found on this page
            for chapter in chapters:
                chapter_texts = chapter.split(index_delimiter)
                chapter_title = chapter_texts[0].replace('…', '').strip()

                # Skip over if chapter is blank, is a page range (e.g. 5-10), or roman numerals (e.g. III)
                if chapter_title.replace('-', '').isdigit() or not chapter.strip() or re.match(r"[IVX]+", chapter):
                    continue

                # If there are no index delimiters, this is a section
                # Set current_section for future chapters to fall under
                elif len(chapter_texts) == 1:
                    print('-- {}'.format(chapter_title))
                    current_section = root_chapter.add_child(chapter_title)
                    continue

                # Chapter has index delimiter, but no page number
                # Match with the page_numbers to assign a page number
                elif not chapter_texts[-1].strip() or any(c for c in chapter_texts[-1] if c.isalpha()):
                    try:
                        chapter_title = "{} {}".format(chapter_texts[-1].replace('…', '').strip(), chapter_title)
                        page_number = page_numbers[page_number_index]
                        page_number_index += 1
                    except IndexError:
                        print('WARNING: Unable to parse {}'.format(chapter))

                # Chapter has index delimiter and page number
                # Assign page number to chapter name
                else:
                    try:
                        page_number = int(''.join([c for c in chapter_texts[-1].split('-')[0] if c.isdigit()]))
                    except ValueError:
                        # If the last item isn't a page number, use the flat
                        # page list to determine the correct page number
                        chapter_title = "{} {}".format(chapter_texts[-1].replace('…', '').strip(), chapter_title)
                        page_number = page_numbers[page_number_index]
                        page_number_index += 1

                # Add the chapter to the current_section
                current_section = current_section or root_chapter
                current_section.add_child(chapter_title, start=page_number)
                print('---- {} {} {}'.format(chapter_title, index_delimiter * 5, page_number))

        # Write -index.json file
        with open(self.index_path, 'wb') as fobj:
            fobj.write(json.dumps(root_chapter.to_dict(), indent=4, ensure_ascii=False).encode('utf-8'))

        return self.index_path


    # -data.json file generation code
    #######################################################################################################
    def get_filename(self, text):
        """
            Returns a valid filename to write split pdf to
            Args: text (str) text to make a valid filepath
            Returns str of valid file or folder name
        """
        return "".join([c for c in text.replace(" ", "-") if c.isalnum() or c == "-"][:30])

    def flatten_dict(self, data):
        """
            Flattens a dictionary into a list of page numbers
            Args: data (dict) dict to flatten
            Returns list of flattened dict
        """
        return list(itertools.chain(*[self.flatten_dict(v)
            if isinstance(v, dict) else [v] for k, v in data.items()
        ]))

    def generate_data_file(self):
        """
            Generates the -data.json file
            Args: None
            Returns: str path to -data.json file

            ---

            See get_data_file docstring for sample -data.json data
        """
        print(os.path.basename(self.download_url))

        # If there's already a -data.json file, return that
        if os.path.exists(self.pdf_data_path):
            print('-- Found data file at {}'.format(self.pdf_data_path))
            return self.pdf_data_path

        # Raise an error if there isn't a corresponding -index.json file
        if not os.path.exists(self.index_path):
            raise OSError('Unable to find index file for {}. Please run scripts/generateindex.py command and try again.'.format(self.download_url))

        # Read the index data
        with open(self.index_path, 'rb') as fobj:
            try:
                chapter_data = json.loads(fobj.read())
            except Exception as e:
                raise OSError('{} is invalid ({}). Please edit file and try again'.format(self.index_path, str(e)))

        # Get flat list of page numbers
        next_pages = iter(sorted(self.flatten_dict(chapter_data['chapters']))[1:])

        # Write pdf data to -data.json path
        pdf_data = self.write_pdf(chapter_data['chapters'], chapter_data['offset'], next_pages)
        with open(self.pdf_data_path, 'wb') as fobj:
            fobj.write(json.dumps(pdf_data, indent=2, ensure_ascii=False).encode('utf-8'))

        return self.pdf_data_path

    def write_pdf(self, chapter_data, offset, pages, folder=''):
        """
            Writes split pdfs
            Args:
                - chapter_data (dict) index data for chapters
                - offset (int) difference between first page number and where first page actually starts
                - pages (list) list of page numbers (used to get where chapter ends)
                - folder (str) name of folder to save pdfs under (important if chapters have the same name)
        """
        book_data = []

        # Iterate through chapter_data
        for title, data in chapter_data.items():
            # Create topics for sections
            if isinstance(data, dict):
                print(title)
                book_data.append({
                    "header": title,
                    "chapters": self.write_pdf(data, offset, pages, folder=title)
                })

            # Create document nodes
            else:
                print('---- {}'.format(title))

                # Get where the page should end
                try:
                    end = next(pages) - 1 + offset
                except StopIteration:
                    end = self.pdf.numPages

                # Split pdf, extract exercises, and add to book_data
                pdf_path = self.write_pages(title, data - 1 + offset, end, folder=self.get_filename(folder))
                exercise_data = self.extract_exercises(pdf_path)
                book_data.append({
                    "chapter": title,
                    "path": pdf_path,
                    "exercises": exercise_data
                })
        return book_data

    def write_pages(self, title, start, end, folder='pdfs'):
        """
            Write a pdf from a given range
            Args:
                - title (str) name of pdf file
                - start (int) starting page number
                - end (int) last page number
                - folder (str) where to store pdf when done (optional)
            Returns str path to file
        """

        # Create a writer and set where to write path to
        writer = PdfFileWriter()
        directory = os.path.sep.join([os.path.dirname(self.path), folder])
        write_to_path = os.path.sep.join([directory, "{}.pdf".format(self.get_filename(title))])

        # If the file already exists, just return the path
        if os.path.exists(write_to_path):
            return write_to_path

        # Create the write-to directory if it doesn't exist already
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Add pages based on the start and end range
        for page in range(start, end):
            try:
                writer.addPage(self.pdf.getPage(page))
            except IndexError:
                raise IndexError('{path} does not contain {num} pages.Please do the following steps to continue:\n'
                    '1. Adjust the offset on the {index} file\n'
                    '2. Rename or delete the {data} file\n'
                    '3. Re-run scripts/generatedata.py\n'
                    '4. Copy over any work from the original {data} file'.format(
                        path=self.download_url, num=end, index=self.index_path, data=self.pdf_data_path
                    ))

        # Write the finished file to the write_to_path
        with open(write_to_path, 'wb') as outfile:
            writer.write(outfile)

        return write_to_path

    def extract_exercises(self, filepath):
        """
            Reads the file and extracts potential exercise questions
            Args: filepath (str) path to file to read
            Returns list of exercise data

            ---

            Sample exercise data:

            [
              {
                "description": "Some exercise description",
                "questions": [
                  {
                    "question": "Which of the following are fruits?",
                    "type": "multiple_selection",
                    "answers": {
                      "Apples": true,
                      "Oranges": true,
                      "Potatoes": false
                    }
                  },
                  {
                    "question": "Can birds fly?",
                    "type": "single_selection",
                    "answers": {
                      "Yes": true,
                      "No": false
                    }
                  }
                ]
              }
            ]
        """
        exercises = []

        # Read file and get text
        page = parser.from_file(filepath)['content']
        if not page:
            return

        # Try to find text that matches the given regex (e.g. "1. Some text")
        for match in re.finditer(r"[1-9]+\.\s*((?:(?![1-9]\.|^[A-Z][^\.]).|\n)+)", page, re.MULTILINE):
            current_exercise = {'description': '', 'questions': []}

            # Extract multiple selection questions (i.e. open-ended questions within the text)
            if 'contestamos' in match.group(1).lower() and re.search(r"\n[a-z]\.", match.group(1)):
                for index, item in enumerate(re.compile(r"\n[a-z]\.").split(match.group(1))):
                    if index == 0:
                        current_exercise['description'] = self.format_exercise_text(item)
                    else:
                        current_exercise['questions'].append({
                            "question": self.format_exercise_text(item),
                            "type": "multiple_selection",
                            "answers": {"Continuar": True }
                        })

            # Extract single selection questions (i.e. select the correct answer from the list)
            elif 'seleccionamos' in match.group(1).lower() and re.search(r"\n[A-Z]\.", match.group(1)):
                for index, item in enumerate(re.compile(r"\n[A-Z]\.").split(match.group(1))):
                    if index == 0:
                        current_exercise['description'] = self.format_exercise_text(item)
                    else:
                        current_question = { "question": "", "type": "single_selection", "answers": {}}

                        # Get question and answers text
                        for i, text in enumerate(re.compile(r"\n[a-z]\.").split(item)):
                            if i == 0:
                                current_question['question'] = self.format_exercise_text(text)
                            else:
                                current_question["answers"].update({self.format_exercise_text(text): i == 1})
                        current_exercise['questions'].append(current_question)

            # Skip any paragraphs that don't match the multiple or single selection question regexes
            else:
                continue

            # Add exercise to exercise data to return
            exercises.append(current_exercise)
        return exercises

    def format_exercise_text(self, text):
        """
            Cleans up the text for exercise questions and answers
            Args: text (str) text to format
            Returns cleaned up exercise str
        """
        return re.sub(r"-\s*\n*\s*", "", text).replace('  ', ' ').replace('¿?', '')\
                .replace('\n', '').strip('\s:').strip()
