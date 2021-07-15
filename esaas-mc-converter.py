import logging
import re
import shutil
import uuid
from argparse import ArgumentParser
from collections import namedtuple
from pathlib import Path

from converter.guides.tools import write_json, read_file, write_file

FileToProcess = namedtuple('FileToProcess', ['name', 'assessment_items'])
AssessmentItem = namedtuple('AssessmentItem', ['type', 'options', 'settings'])

SELECT_MULTIPLE = 'select_multiple'
PAGE = 'page'


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


def get_assessment_item(assessment, name, count):
    instructions = ''
    guidance = []
    answers = []

    for option in assessment.options:
        option_type = option[0].strip()
        if option_type == 'group':
            continue
        if option_type == 'tags':
            continue
        if option_type == 'text':
            instructions = option[1] if option[1] != "" else option[2]
            continue
        if option_type == 'answer' or option_type == 'distractor':
            match_guidance = re.search(r"\s+:explanation => (?P<explanation>.*?)$", option[1], flags=re.MULTILINE)
            if match_guidance:
                guidance.append(match_guidance.group('explanation'))
            answers.append(get_assessment_answer(option))

    return {
        "type": "multiple-choice",
        "taskId": f"multiple-choice-{slugify(name)}-{count}",
        "source": {
            "name": f"{name} {count}",
            "showName": True,
            "instructions": instructions.replace("\\n", ""),
            "multipleResponse": assessment.type == SELECT_MULTIPLE,
            "isRandomized": assessment.settings.get('randomize', False),
            "answers": answers,
            "guidance": '\n\n'.join(guidance),
            "showGuidanceAfterResponseOption": {
                "type": "Always"
            },
            "showExpectedAnswer": True,
            "points": int(assessment.settings.get('points', 20)),
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


def get_assessment_answer(option):
    answer = re.sub(r"(.*?),\s+:explanation => .*?$", r"\1", option[1], flags=re.MULTILINE)
    return {
        "_id": str(uuid.uuid4()),
        "correct": option[0] == 'answer',
        "answer": answer.replace("\\n", "")
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
    write_file(content_file, f'{base_content}\n')
    section['content-file'] = str(str(relative_path).replace("\\", "/"))
    return section


def convert_to_codio_structure(to_process):
    structure = []
    sections = []
    assessments = []

    for item in to_process:
        book_item = get_book_item(item.name, PAGE)
        structure.append(book_item)

        files = [
            {
                "action": "close",
                "path": "#tabs"
            }
        ]
        content = generate_content(item.name, item.assessment_items)
        current_item = get_section_item(item.name, files)
        current_item['content-file'] = '\n'.join(content)
        sections.append(current_item)

        assessment_count = 0
        for assessment in item.assessment_items:
            assessment_count += 1
            assessments.append(get_assessment_item(assessment, item.name, assessment_count))

    return structure, sections, assessments


def generate_content(assessment_name, assessment_items):
    count = 0
    current_content = []
    for _ in assessment_items:
        count += 1
        current_content.append(f"{{Check It!|assessment}}(multiple-choice-{slugify(assessment_name)}-{count})\n")
    return current_content


def convert(base_directory, output_dir):
    shutil.rmtree(output_dir, ignore_errors=True)
    to_process = []
    for file in (base_directory.glob('*.rb')):
        assessment_items = []
        file_data = read_file(file.resolve())

        match_data = re.search(r"^quiz\s+['\"](?P<name>.*?)['\"]\s+(?:do)?\n(?P<assessments_block>.*(?=end))",
                               file_data, flags=re.MULTILINE + re.DOTALL)

        if not match_data:
            return
        name = match_data.group('name').strip()
        assessments_block = match_data.group('assessments_block')
        assessments_block = re.sub(r"^\s+#+$", "", assessments_block, flags=re.MULTILINE)
        assessments_block += "\n"

        result = re.finditer(r"^\s+(?P<type>choice_answer|select_multiple)(?P<settings>\s+:.*? => ?.*?)?\s+do\n"
                             r"(?P<content>.*?)(?:\s+end\s+\n(?!\n\s*\S)|(?=\s+\1))",
                             assessments_block, flags=re.MULTILINE + re.DOTALL + re.VERBOSE)
        if not result:
            print(file, 'PARSE ERROR')
            return
        print(file)

        for item in list(result):
            mc_type = item.group('type')
            content = item.group('content')

            settings = {}
            match_settings = item.group('settings')
            if match_settings is not None:
                for settings_item in match_settings.split(','):
                    match_settings_item = re.search(r":((?P<key>.*?) => (?P<value>.*?))$", settings_item,
                                                    flags=re.MULTILINE)
                    if match_settings_item:
                        settings[match_settings_item.group('key')] = match_settings_item.group('value')

            options = re.findall(r"\s+(?:#[ ])?(?P<option>.*?)\s+(?:['\"](?P<value>.*?)['\"]$"
                                 r"|%[qQ]{(?P<another_value>.*?)})", content + '\n', flags=re.MULTILINE + re.DOTALL)
            assessment_items.append(AssessmentItem(mc_type, options, settings))

        to_process.append(FileToProcess(name, assessment_items))

    structure, sections, assessments = convert_to_codio_structure(to_process)

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
