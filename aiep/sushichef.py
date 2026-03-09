#!/usr/bin/env python
import os
import tempfile
import xlrd
import zipfile
from le_utils.constants import exercises
from le_utils.constants import licenses
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import (
    TopicNode,
    DocumentNode,
    H5PAppNode,
    ExerciseNode,
    VideoNode,
)
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.classes.files import DocumentFile, H5PFile, VideoFile
from ricecooker.classes.licenses import get_license

AIEP_License = get_license(
    licenses.SPECIAL_PERMISSIONS,
    copyright_holder="AIEP",
    description="Todos los derechos reservados",
)


def leer_preguntas(filename):
    def get_question():
        return SingleSelectQuestion(
            id="ejemplo_Q{}".format(n),
            question=question,
            all_answers=answers,
            correct_answer=correct,
        )

    questions = []
    wb = xlrd.open_workbook(filename, formatting_info=True)
    sheet = wb.sheet_by_index(0)
    question = ""
    answers = []
    correct = ""
    for n in range(sheet.nrows):
        row_text = sheet.cell_value(n, 0)
        if not question:
            question = row_text
        elif not row_text:
            # ended question
            questions.append(get_question())
            question = ""
            answers = []
        else:
            answers.append(row_text)
            if sheet.cell_xf_index(n, 0) != 21:  # no back color
                correct = row_text
    questions.append(get_question())  # add the last question dict
    return questions


def get_title_from_video(title, filename):
    if "dummy" in filename:
        return "Vídeo explicativo de la {}".format(title)
    else:
        words = filename.split("-")[:-1]
        if len(words) > 1:  # uses slashes to split words
            new_title = " ".join(filename.split("-")[:-1])
        else:
            # just remove the file extension:
            new_title = os.path.splitext(filename)[0]

        return new_title.capitalize()

def get_video_from_h5p(filename):
    mp4_file = None
    with zipfile.ZipFile(filename, "r") as my_h5p:
        list_of_files = my_h5p.namelist()
        mp4s = [f for f in list_of_files if f.endswith(".mp4")]
        mp4_content = [f for f in mp4s if "content/videos" in f]
        if len(mp4_content) == 1:
            mp4_file = my_h5p.extract(mp4_content[0], tempfile.mkdtemp())

    return mp4_file


def get_files(topic_name, directory, files):
    topic = TopicNode(title=topic_name, source_id="{}_id".format(topic_name))
    for filename in files:
        if filename.endswith("h5p"):
            title = None
        else:
            title = os.path.splitext(filename)[0]
        node = get_file(topic_name, directory, filename, title)
        if node:
            topic.add_child(node)
    return topic


def get_file(name, directory, filename, title=None):
    filepath = os.path.join(directory, filename)
    if title is None:
        title = name
    source_id = "{}/{}".format(name, filename)
    node = None
    if filename.endswith(".pdf"):
        node = DocumentNode(
            title=title,
            description="Documentación de {}".format(name),
            source_id=source_id,
            license=AIEP_License,
            language="es",
            files=[
                DocumentFile(
                    path=filepath,
                    language="es",
                )
            ],
        )
    elif filename.endswith("h5p"):
        mp4_file = get_video_from_h5p(filepath)
        if mp4_file is None:
            classNode = H5PAppNode
            classFile = H5PFile
        else:
            classNode = VideoNode
            classFile = VideoFile
            filepath = mp4_file

        node = classNode(
            title=get_title_from_video(title, filename),
            description="Vídeo explicativo de la {}".format(name),
            source_id=source_id,
            license=AIEP_License,
            language="es",
            files=[
                classFile(
                    path=filepath,
                    language="es",
                )
            ],
        )

    elif filename.endswith("xls"):
        node = ExerciseNode(
            source_id=source_id,
            title="Ejercicios de {}".format(name),
            author="Equipo de AIEP",
            description="Preguntas de la unidad 1",
            language="es",
            license=AIEP_License,
            thumbnail=None,
            exercise_data={
                "mastery_model": exercises.M_OF_N,  # \
                "m": 2,  # learners must get 2/3 questions correct to complete
                "n": 3,  # /
                "randomize": True,  # show questions in random order
            },
            questions=leer_preguntas(filepath),
        )

    return node


def get_course(course, base_path):
    topic = TopicNode(title=course, source_id="{}_id".format(course))
    course_dir = os.path.join(base_path, course)
    course_contents = os.listdir(course_dir)
    course_contents.sort()
    for f in course_contents:
        content = os.path.join(course_dir, f)
        if os.path.isdir(content):
            total_files = os.listdir(content)
            if len(total_files) > 1:
                node = get_files(f, content, total_files)
                if node:
                    topic.add_child(node)
            elif len(total_files) == 1:
                topic.add_child(get_file(f, content, total_files[0]))
    return topic


class AIEPChef(SushiChef):

    channel_info = {
        "CHANNEL_TITLE": "Canal de AIEP",
        "CHANNEL_SOURCE_DOMAIN": "www.aiep.cl",
        "CHANNEL_SOURCE_ID": "aiep",
        "CHANNEL_LANGUAGE": "es",
        "CHANNEL_THUMBNAIL": "https://www.aiep.cl/img/logo-400x140.png",
        "CHANNEL_DESCRIPTION": "Cursos preparados por AIEP  (Chile)",
    }

    # SETTINGS = {"path": "/datos/le/un-women/AIEPOneDrive_2021-02-17/H5P ONU"}

    def construct_channel(self, *args, **kwargs):
        BASE_PATH = kwargs.get("path", "./AIEPOneDrive")
        channel = self.get_channel(*args, **kwargs)
        root_contents = os.listdir(BASE_PATH)
        courses = []
        for f in root_contents:
            if os.path.isdir(os.path.join(BASE_PATH, f)):
                courses.append(f)
        courses.sort()
        for course in courses:
            channel.add_child(get_course(course, BASE_PATH))
        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --token=YOURTOKENHERE9139139f3a23232 path="/AIEPOneDrive_2021-02-17/H5P ONU"

    In kolibri this is needed:
      `kolibri plugin enable kolibri.plugins.h5p_viewer`

    """
    chef = AIEPChef()
    chef.main()
