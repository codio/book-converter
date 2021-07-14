import logging
import re
import shutil
import uuid
from argparse import ArgumentParser
from collections import namedtuple
from pathlib import Path

from converter.guides.tools import write_json, read_file, write_file

FileToProcess = namedtuple('FileToProcess', ['name', 'mc_items'])
AssessmentItem = namedtuple('AssessmentItem', ['type', 'options'])

SELECT_MULTIPLE = 'select_multiple'


def slugify(in_str):
    return re.sub('[^a-zA-Z0-9]+', '', in_str).lower()


def get_book_item(name, item_type):
    generated_item = {
        "id": slugify(name),
        "title": name,
        "type": item_type,
        'pageId': slugify(name)
    }
    return generated_item


def get_section_item(name, files):
    return {
        "id": slugify(name),
        "title": name,
        "files": files,
        "path": [],
        "type": "markdown",
        "content-file": "",
        "chapter": False,
        "reset": [],
        "teacherOnly": False,
        "learningObjectives": ""
    }


def get_assessment_item(assessment, name, assessment_count):
    instructions = ''
    answer_count = 0
    answers = []
    for opt in assessment.options:
        if opt[0] == 'text':
            instructions = opt[1]
        answer_count += 1
        answers.append(get_mc_answers(opt, answer_count))

    return {
        "type": "multiple-choice",
        "taskId": f"multiple-choice-{slugify(name)}-{assessment_count}",
        "source": {
            "name": f"{name} {assessment_count}",
            "showName": True,
            "instructions": instructions,
            "multipleResponse": assessment.type == SELECT_MULTIPLE,
            "isRandomized": True,
            "answers": answers,
            "guidance": "",
            "showGuidanceAfterResponseOption": {
                "type": "Never"
            },
            "showExpectedAnswer": True,
            "points": 20,
            "incorrectPoints": 0,
            "arePartialPointsAllowed": False,
            "metadata": {
                "tags": [
                    {
                        "name": "Assessment Type",
                        "value": "Multiple Choice"
                    }
                ],
                "files": [],
                "opened": []
            },
            "bloomsObjectiveLevel": "",
            "learningObjectives": ""
        }
    }


def get_mc_answers(opt, count):
    return {
        "_id": str(uuid.uuid4()),
        "correct": opt[0] == 'answer',
        "answer": f"{count}"
    }


def full_book_structure(structure):
    return {
        "name": "ESaaS multiple choice assessments",
        "children": structure
    }


def full_metadata(structure):
    return {
        "theme": "light",
        "scripts": [],
        "lexikonTopic": "",
        "useSubmitButtons": True,
        "useMarkAsComplete": True,
        "sections": structure
    }


def write_section_files(section, output_dir):
    name = section['id']
    content_file = output_dir.joinpath('.guides/content').joinpath(f'{name}.md')
    content_file.parent.mkdir(parents=True, exist_ok=True)
    relative_path = content_file.relative_to(output_dir)
    base_content = section.get('content-file', '')
    content = f'{base_content}\n'
    write_file(content_file, content)
    section['content-file'] = str(str(relative_path).replace("\\", "/"))
    return section


def get_codio_structure(to_process):
    structure = []
    sections = []
    assessments = []

    for item in to_process:
        book_item = get_book_item(item.name, "chapter")
        structure.append(book_item)
        files = [
            {
                "action": "close",
                "path": "#tabs"
            }
        ]
        content = generate_content(item.name, item.mc_items)
        current_item = get_section_item(item.name, files)
        current_item['content-file'] = '\n'.join(content)
        sections.append(current_item)

        assessment_count = 0
        for assessment in item.mc_items:
            assessment_count += 1
            assessments.append(get_assessment_item(assessment, item.name, assessment_count))

    return structure, sections, assessments


def generate_content(assessment_name, mc_items):
    count = 0
    current_content = []
    for _ in mc_items:
        count += 1
        current_content.append(f"{{Check It!|assessment}}(multiple-choice-{slugify(assessment_name)}-{count})")
    return current_content


def convert(base_directory, output_dir):
    shutil.rmtree(output_dir, ignore_errors=True)

    to_process = []
    for file in (base_directory.glob('*.rb')):
        file_data = read_file(file.resolve())

        match_title = re.search(r"^quiz[ ]['\"](?P<name>.*?)['\"](?:[ ]do)?$", file_data, flags=re.MULTILINE)
        if not match_title:
            print(file, 'PARSE ERROR')
            return
        name = match_title.group('name').strip()
        print(file)

        mc_items = []
        result = re.finditer(r"^[ ]+(?P<type>choice_answer|select_multiple).*?\n(?P<content>.*?)[ ]{2}end", file_data,
                             flags=re.MULTILINE + re.DOTALL)

        for item in list(result):
            mc_type = item.group('type')
            content = item.group('content')
            options = re.findall(r"[ ]{4}(?P<option>.*?)[ ]['\"](?P<value>.*?)['\"]\n", content)
            mc_items.append(AssessmentItem(mc_type, options))

        to_process.append(FileToProcess(name, mc_items))

    structure, sections, assessments = get_codio_structure(to_process)

    output_dir.mkdir()
    guides_dir = output_dir.joinpath('.guides')
    guides_dir.mkdir()
    book_file = guides_dir.joinpath('book.json').resolve()
    write_json(book_file, full_book_structure(structure), False)

    updated_sections = list(map(lambda section: write_section_files(section, output_dir), sections))
    metadata_file = guides_dir.joinpath('metadata.json')
    write_json(metadata_file, full_metadata(updated_sections), False)

    assessments_file = guides_dir.joinpath('assessments.json')
    write_json(assessments_file, assessments, False)


def main():
    parser = ArgumentParser(description='Process convert esaas mc (RUQL) to codio mc format.')
    parser.add_argument('paths', metavar='PATH', type=str, nargs='+', help='path to a sources directory')
    parser.add_argument('-l', '--log', action='store', default=None)
    parser.add_argument('--output', type=str, help='path to output folder')

    args = parser.parse_args()

    logging.basicConfig(filename=args.log, level=logging.DEBUG,
                        format='[%(asctime)s] %(levelname).5s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')

    for path in args.paths:
        convert(Path(path), Path(args.output))


if __name__ == '__main__':
    main()
