import logging
import pathlib
import re
import shutil
import uuid
import yaml

from collections import OrderedDict
from pathlib import Path

from converter.opendsa_assessments.code_workout import create_assessments_data
from converter.rst2markdown import Rst2Markdown
from converter.toc import get_latex_toc, get_bookdown_toc, get_rst_toc
from converter.guides.tools import slugify, write_file, write_json, parse_csv_lines
from converter.guides.item import SectionItem, CHAPTER
from converter.latex2markdown import LaTeX2Markdown
from converter.bookdown2markdown import BookDown2Markdown
from converter.assets import copy_assets, convert_assets, process_source_code, copy_files_from_bookdown_folder
from converter.refs import make_refs, override_refs, get_ref_chapter_counter_from, make_bookdown_refs
from converter.optimizer import optimize


def get_guide_content_path(file_path):
    file_path = str(file_path)
    pos = file_path.find(".guides")
    if pos == -1:
        return file_path
    return file_path[pos:]


def prepare_codio_rules(config):
    chapter = None
    rules = {}
    sections = config.get('sections', list())
    for section in sections:
        if section["type"] == CHAPTER:
            slug_name = slugify(section["name"])
            chapter = section["name"]
        else:
            slug_name = slugify(section["name"], chapter=chapter)
        section["slug"] = slug_name
        rules[slug_name] = section

    insert_rules = {}
    insert_sections = config.get('insert_sections', [])
    for section in insert_sections:
        position = slugify(section["section"], chapter=section["chapter"])
        section["position"] = position
        insert_rules.setdefault(position, []).append(section)

    return rules, insert_rules


def cleanup_latex(lines):
    updated = []
    starts = (
        '%', '\\index{', '\\markboth{', '\\addcontentsline{',
        '\\vspace', '\\newpage', '\\noindent',
        '\\ttfamily', '\\chapter', '\\section', '\\newcommand', '\\vfill', '\\pagebreak'
    )
    for line in lines:
        if line.startswith(starts):
            continue
        updated.append(line)
    return updated


def make_relative(i, item):
    copied = i.copy()
    copied["position"] = int(copied.get("position")) - item.line_pos
    return copied


def modify_rules_position(rules, start_position, delta):
    for rule in rules:
        position = rule.get('position')
        if position < start_position:
            continue
        rule['position'] = rule['position'] + delta


def apply_codio_rules_to_item(item, rules):
    relative = map(lambda i: make_relative(i, item), rules)
    sorted_rules = sorted(relative, key=lambda i: i.get("position"))

    tokens = {}

    pos = 0
    for rule in sorted_rules:
        position = rule.get('position')
        pos += 1
        if position < 0 or position > len(item.lines) + 1:
            logging.info("wrong rule position, it will be ignored %s", rules[pos - 1])
            continue
        if 'add' in rule:
            text = rule.get('add')
            token = str(uuid.uuid4())
            tokens[token] = text
            item.lines.insert(position, token)
            modify_rules_position(sorted_rules, position, 1)
        if 'remove' in rule:
            count = rule.get('remove', 1)
            for _ in range(count):
                item.lines.pop(position)
            modify_rules_position(sorted_rules, position, 0 - count)

    return tokens


def generate_insert_items(insert_rules, slug_name):
    inserts_before = []
    inserts_after = []
    if slug_name in insert_rules:
        rules = insert_rules[slug_name]
        for rule in rules:
            insert_item = SectionItem(section_name=rule.get('name'), section_type=rule.get('type'), line_pos=1)
            latex = rule.get('latex')
            markdown = rule.get('markdown')
            before = rule.get('before', False)
            insert_item.codio_section = rule.get('codio_section')
            if latex:
                insert_item.lines = latex.split('\n')
            elif markdown:
                insert_item.markdown = markdown
            else:
                continue
            if before:
                inserts_before.append(insert_item)
            else:
                inserts_after.append(insert_item)
    return inserts_before, inserts_after


def codio_transformations(toc, transformation_rules, insert_rules):
    updated_toc = []
    chapter = None
    tokens = {}

    for item in toc:
        if item.section_type == CHAPTER:
            slug_name = slugify(item.section_name)
            chapter = item.section_name
        else:
            slug_name = slugify(item.section_name, chapter=chapter)

        skip = False

        if slug_name in transformation_rules:
            rules = transformation_rules[slug_name].get("transformations")
            codio_section = transformation_rules[slug_name].get('codio_section', None)
            if codio_section:
                item.codio_section = codio_section
            if isinstance(rules, str) and rules == "skip":
                skip = True
            elif isinstance(rules, list) and rules:
                tokens[slug_name] = apply_codio_rules_to_item(item, rules)

        inserts_before, inserts_after = generate_insert_items(insert_rules, slug_name)

        if inserts_before:
            updated_toc += inserts_before

        if not skip:
            updated_toc.append(item)

        if inserts_after:
            updated_toc += inserts_after

    return updated_toc, tokens


def prepare_base_directory(generate_dir, yes=False):
    if generate_dir.exists():
        if not yes:
            name = input("destination directory exists, continue? Y/n: ")
            if name.lower().strip() == 'n':
                return False
        shutil.rmtree(generate_dir, ignore_errors=True)
    return True


def prepare_structure(generate_dir):
    generate_dir.mkdir()
    guides_dir = generate_dir.joinpath(".guides")
    guides_dir.mkdir()
    content_dir = guides_dir.joinpath("content")
    content_dir.mkdir()

    return guides_dir, content_dir


def make_metadata_items(config):
    book = {
        "name": "TODO: book name",
        "children": []
    }
    metadata = {
        "sections": [],
        "theme": "light",
        "scripts": [],
        "lexikonTopic": "",
        "suppressPageNumbering": False,
        "useSubmitButtons": True,
        "useMarkAsComplete": True,
        "hideMenu": False,
        "allowGuideClose": False,
        "collapsedOnStart": False,
        "hideSectionsToggle": False,
        "hideBackToDashboard": False,
        "protectLayout": False
    }

    predefined_metadata = config.get('metadata', {})
    metadata = {**metadata, **predefined_metadata}

    return book, metadata


def get_section_type(item):
    if item.codio_section == "start":
        return "section"
    return "chapter" if item.section_type == CHAPTER else "page"


def fix_title(name):
    if '----' in name:
        return name[name.find('----') + 4:]
    return name


def make_section_items(item, slug_name, md_path, transformation_rules, converted_md):
    book_item = {
        "id": slug_name,
        "title": fix_title(item.section_name),
        "type": get_section_type(item),
        "pageId": slug_name
    }
    section = {
        "id": slug_name,
        "title": fix_title(item.section_name),
        "files": [],
        "path": [],
        "type": "markdown",
        "content-file": get_guide_content_path(md_path),
        "chapter": True if item.section_type == CHAPTER else False,
        "reset": [],
        "teacherOnly": False,
        "learningObjectives": ""
    }
    if slug_name in transformation_rules:
        configuration = transformation_rules[slug_name].get('configuration', {})
        if configuration:
            section = {**section, **configuration}
    # if not converted_md:
    #     del book_item["pageId"]
    #     section = None
    return section, book_item


def make_odsa_ex_files(path):
    path = path.replace("\\", "/")
    return {
               "path": "#tabs",
               "action": "close"
           }, {
               "path": f"exercises/{path}/starter_code.java",
               "panel": 0,
               "action": "open"
           }


def process_assets(config, generate_dir, pdfs_for_convert, source_codes, bookdown=False):
    logging.debug("copy assets")
    copy_assets(config, generate_dir)

    if bookdown:
        copy_files_from_bookdown_folder(config, generate_dir)

    if pdfs_for_convert:
        logging.debug("convert included pdfs")
        convert_assets(config, generate_dir, pdfs_for_convert, bookdown=bookdown)

    if source_codes:
        logging.debug("process source codes")
        use_code_folder = bool(config.get('workspace', {}).get('useCodeFolder', True))
        process_source_code(source_codes, generate_dir, use_code_folder)

    optimization_config = config.get('optimization', {})
    if optimization_config:
        optimize(optimization_config, generate_dir)


def write_metadata(guides_dir, metadata, book):
    logging.debug("write metadata")

    metadata_path = guides_dir.joinpath("metadata.json")
    book_path = guides_dir.joinpath("book.json")
    write_json(metadata_path, metadata)
    write_json(book_path, book)


def convert_assessment(assessment):
    if assessment.type == 'custom':
        return convert_custom_assessment(assessment)
    elif assessment.type == 'test':
        return convert_code_workout_assessment(assessment)


def convert_custom_assessment(assessment):
    return {
        'type': 'custom',
        'taskId': assessment.id,
        'source': {
            'name': assessment.name,
            'arePartialPointsAllowed': False,
            'oneTimeTest': False,
            'points': assessment.points,
            'instructions': assessment.ex_data.get('question', '')
        }
    }


def convert_code_workout_assessment(assessment):
    class_name = assessment.ex_data.get('class_name', '')
    method_name = assessment.ex_data.get('method_name', '')
    instructions = assessment.ex_data.get('question', '')
    instructions = re.sub(r'<img src=\"http://.*?(Exercises.*?)\">',
                          r'<img src=".guides/opendsa_v1/\1">', instructions)
    ex_path = assessment.ex_data.get('ex_path', '')
    tests = assessment.ex_data.get('tests', '')
    test_matches = parse_csv_lines(tests)
    instructions = instructions_with_examples(test_matches, instructions, method_name)
    return {
        'type': 'test',
        'taskId': assessment.id,
        'source': {
            'name': assessment.name,
            'instructions': instructions,
            'command': f'.guides/secure/assessments/run.py {class_name} {ex_path}',
            'arePartialPointsAllowed': True,
            'oneTimeTest': False,
            'points': assessment.points
        }
    }


def instructions_with_examples(test_matches, instructions, method_name):
    examples_list = []
    examples = ''
    for item in test_matches:
        example = _get_example(item, method_name)
        if example:
            examples_list.append(example)
    if examples_list:
        examples = '\n'.join(examples_list)
        examples = f'\nExamples:\n\n{examples}'
    return f'{instructions}{examples}'


def _get_example(item, method_name):
    example = None
    message = item[2] if len(item) == 3 else None
    if message and message == 'example':
        actual = item[0]
        actual = re.sub(r'new\s+[a-zA-Z0-9]+(\s*\[\s*])+\s*', '', actual)
        expected = item[1]
        example = f'`{method_name}({actual}) -> {expected}`\n\n'
    return example


def write_assessments(guides_dir, assessments):
    if not assessments:
        return
    logging.debug("write assessments")
    assessments_path = guides_dir.joinpath("assessments.json")

    unique_assessments = list({object_.id: object_ for object_ in assessments}.values())

    converted_assessments = list(map(convert_assessment, unique_assessments))
    write_json(assessments_path, converted_assessments)


def convert(config, base_path, yes=False):
    base_dir = base_path
    generate_dir = base_dir.joinpath("generate")
    if not prepare_base_directory(generate_dir, yes):
        return

    logging.debug("start converting %s" % generate_dir)
    guides_dir, content_dir = prepare_structure(generate_dir)
    transformation_rules, insert_rules = prepare_codio_rules(config)
    toc = get_latex_toc(Path(config['workspace']['directory']), Path(config['workspace']['tex']))
    toc, tokens = codio_transformations(toc, transformation_rules, insert_rules)
    refs = make_refs(toc, chapter_counter_from=get_ref_chapter_counter_from(config))
    refs = override_refs(refs, config)
    book, metadata = make_metadata_items(config)
    remove_trinket = config['workspace'].get('removeTrinket', False)
    remove_exercise = config['workspace'].get('removeExercise', False)

    detect_asset_ext = assets_extension(Path(config['workspace']['directory']))

    chapter = None
    children_containers = [book["children"]]
    chapter_num = get_ref_chapter_counter_from(config) - 1
    figure_num = 0
    exercise_num = 0
    pdfs_for_convert = []
    source_codes = []
    logging.debug("convert selected pages")

    for item in toc:
        if item.section_type == CHAPTER:
            chapter_num += 1
            figure_num = 0
            exercise_num = 0
            slug_name = slugify(item.section_name)
            chapter = item.section_name
        else:
            slug_name = slugify(item.section_name, chapter=chapter)

        logging.debug("convert page {} - {}".format(slug_name, chapter_num))

        converted_md = item.markdown

        if not converted_md:
            lines = cleanup_latex(item.lines)

            md_converter = LaTeX2Markdown(
                lines,
                refs=refs, chapter_num=chapter_num, figure_num=figure_num,
                exercise_num=exercise_num, remove_trinket=remove_trinket,
                remove_exercise=remove_exercise, detect_asset_ext=detect_asset_ext,
                load_workspace_file=workspace_file(Path(config['workspace']['directory'])),
                code_syntax=config.get('code_syntax', 'code')
            )

            converted_md = md_converter.to_markdown()
            figure_num += md_converter.get_figure_counter()
            exercise_num += md_converter.get_exercise_counter()

            if md_converter.get_pdfs_for_convert():
                pdfs_for_convert += md_converter.get_pdfs_for_convert()

            if md_converter.get_source_codes():
                source_codes += md_converter.get_source_codes()

            if slug_name in tokens:
                for key, value in tokens.get(slug_name).items():
                    converted_md = converted_md.replace(key, value)

        md_path = content_dir.joinpath(slug_name + ".md")
        section, book_item = make_section_items(item, slug_name, md_path, transformation_rules, converted_md)

        if item.section_type == CHAPTER or item.codio_section == "start":
            book_item["children"] = []
            if item.section_type == CHAPTER:
                children_containers = [children_containers[0]]
        elif item.codio_section == "end" and len(children_containers) > 1:
            children_containers.pop()

        children_containers[len(children_containers) - 1].append(book_item)

        if item.section_type == CHAPTER or item.codio_section == "start":
            children_containers.append(book_item["children"])
        if section:
            metadata["sections"].append(section)

        write_file(md_path, converted_md)

    write_metadata(guides_dir, metadata, book)
    process_assets(config, generate_dir, pdfs_for_convert, source_codes)


def workspace_file(base_src_dir):
    def load_workspace_file(path):
        if '.' not in path:
            path = f"{path}.tex"
        file = base_src_dir.joinpath(path)
        if file.exists():
            with open(file, 'r', errors='replace') as file:
                return file.read()
        return ''

    return load_workspace_file


def assets_extension(base_src_dir):
    possible_exts = ['pdf', 'png', 'jpg']

    def detect_asset_ext(asset_path):
        for ext in possible_exts:
            file = base_src_dir.joinpath('_bookdown_files').joinpath('{}.{}'.format(asset_path, ext))
            if file.exists():
                return ext
            file = base_src_dir.joinpath('{}.{}'.format(asset_path, ext))
            if file.exists():
                return ext

    return detect_asset_ext


def cleanup_bookdown(lines):
    lines = lines[1:]
    return lines


def cleanup_rst(lines):
    updated = []
    starts = (
        '.. index::'
    )
    for line in lines:
        if line.startswith(starts):
            continue
        updated.append(line)
    return updated


def get_labels(lines):
    label = ''
    for line in lines:
        if line.startswith('.. _'):
            label = line.strip()[4:-1]
    return label


def convert_bookdown(config, base_path, yes=False):
    base_dir = base_path
    generate_dir = base_dir.joinpath("generate")
    if not prepare_base_directory(generate_dir, yes):
        return

    logging.debug("start converting %s" % generate_dir)
    guides_dir, content_dir = prepare_structure(generate_dir)
    transformation_rules, insert_rules = prepare_codio_rules(config)
    toc = get_bookdown_toc(Path(config['workspace']['directory']), Path(config['workspace']['bookdown']))
    toc, tokens = codio_transformations(toc, transformation_rules, insert_rules)
    book, metadata = make_metadata_items(config)

    chapter = None
    chapter_num = get_ref_chapter_counter_from(config) - 1
    figure_num = 0
    children_containers = [book["children"]]
    pdfs_for_convert = []
    logging.debug("convert selected pages")

    detect_asset_ext = assets_extension(Path(config['workspace']['directory']))
    refs = make_bookdown_refs(config)

    for item in toc:
        if item.section_type == CHAPTER:
            chapter_num += 1
            figure_num = 0
            slug_name = slugify(item.section_name)
            chapter = item.section_name
        else:
            slug_name = slugify(item.section_name, chapter=chapter)

        logging.debug("convert page {} - {}".format(slug_name, chapter_num))

        converted_md = item.markdown

        if not converted_md:
            lines = cleanup_bookdown(item.lines)
            md_converter = BookDown2Markdown(
                lines,
                chapter_num=chapter_num, figure_num=figure_num, assets_extension=detect_asset_ext, refs=refs
            )
            figure_num += md_converter.get_figure_counter()
            converted_md = md_converter.to_markdown()
            if md_converter.get_pdfs_for_convert():
                pdfs_for_convert += md_converter.get_pdfs_for_convert()

            if slug_name in tokens:
                for key, value in tokens.get(slug_name).items():
                    converted_md = converted_md.replace(key, value)

        md_path = content_dir.joinpath(slug_name + ".md")
        section, book_item = make_section_items(item, slug_name, md_path, transformation_rules, converted_md)

        if item.section_type == CHAPTER or item.codio_section == "start":
            book_item["children"] = []
            if item.section_type == CHAPTER:
                children_containers = [children_containers[0]]
        elif item.codio_section == "end" and len(children_containers) > 1:
            children_containers.pop()

        children_containers[len(children_containers) - 1].append(book_item)

        if item.section_type == CHAPTER or item.codio_section == "start":
            children_containers.append(book_item["children"])

        if section:
            metadata["sections"].append(section)

        write_file(md_path, converted_md)

    write_metadata(guides_dir, metadata, book)

    process_assets(config, generate_dir, pdfs_for_convert, [], bookdown=True)


def get_code_exercises(workspace_dir):
    exercises = {}
    code_dir = workspace_dir.joinpath('ODSAprivate-master')
    code_dir = pathlib.Path(code_dir)
    if not code_dir.exists():
        return {}
    ex_dirs = [p for p in code_dir.iterdir() if not p.is_file()]
    for directory in ex_dirs:
        yaml_files = directory.glob("*.yaml")
        ex_group_dir = pathlib.Path(directory).name
        ex_group_dir = Path(ex_group_dir)
        for file in yaml_files:
            with open(file, 'r') as stream:
                try:
                    data = yaml.load(stream, Loader=yaml.FullLoader)
                    ex_path = ex_group_dir.joinpath(file.stem)
                    if isinstance(data, list):
                        data = data[0]
                    curr_ver = data.get('current_version', '')
                    prompts = curr_ver.get('prompts', '')[0]['coding_prompt']
                    name = data.get('name', '').lower()
                    exercises[name] = {
                        'name': name,
                        'ex_path': str(ex_path),
                        'file_name': file.stem,
                        'dir_name': directory.name,
                        'class_name': prompts.get('class_name', ''),
                        'method_name': prompts.get('method_name', ''),
                        'question': prompts.get('question', ''),
                        'starter_code': prompts.get('starter_code', ''),
                        'wrapper_code': prompts.get('wrapper_code', ''),
                        'tests': prompts.get('tests', '')
                    }
                except yaml.YAMLError as exc:
                    logging.error("load file exception", exc)
                    raise BaseException("load file exception")
    return exercises


def process_iframe_images(config, generate_dir, iframe_images):
    write_iframe = bool(config.get('opendsa', {}).get('writeIframe', False))
    if write_iframe and iframe_images:
        for image in iframe_images:
            write_path = generate_dir.joinpath(image.path)
            write_path.parent.mkdir(exist_ok=True, parents=True)
            write_file(write_path, image.content)


def prepare_figure_numbers(toc):
    tag_references = dict()
    chapter_num = 0
    subsection_num = 0
    for item in toc:
        if item.section_type == CHAPTER:
            subsection_num = 0
            chapter_num += 1
        else:
            subsection_num += 1

        prepare_figure_numbers_for_item(item, chapter_num, subsection_num, tag_references)
    return tag_references


def prepare_figure_numbers_for_item(item, chapter_num, subsection_num, tag_references):
    figure_counter = 1
    for i in range(len(item.lines)):
        tag = re.search(r"""(\.\.[ ]_(?P<name>[a-zA-Z0-9]*):)""", item.lines[i])
        if tag:
            tag = tag.group('name')
            tag_references[tag] = f'{chapter_num}.{subsection_num}.{figure_counter}'

        matchobj = re.search(r"""(\.\.[ ](?P<figure_type>[a-z]*)::)""", item.lines[i])
        figure_type = matchobj.group('figure_type') if matchobj and matchobj.group('figure_type') is not None else False
        if figure_type and figure_type in ['odsafig', 'figure', 'inlineav', 'topic']:
            item.lines[i] = item.lines[i].replace(
                f'{figure_type}::',
                f'{figure_type}:: :figure_number:{chapter_num}.{subsection_num}.{figure_counter}:')
            figure_counter += 1


def print_source_code_report(data):
    print('\n########## Source code report ##########\n')
    [print(f'{item[0]} | {item[1]} | {item[2]}') for item in data]


def convert_rst(config, base_path, yes=False):
    generate_dir = base_path.joinpath("generate")
    if not prepare_base_directory(generate_dir, yes):
        return
    logging.debug("start converting %s" % generate_dir)
    guides_dir, content_dir = prepare_structure(generate_dir)
    transformation_rules, insert_rules = prepare_codio_rules(config)
    workspace_dir = Path(config['workspace']['directory'])
    source_code = config.get('opendsa', {}).get('source_code', 'java')
    exercises = get_code_exercises(workspace_dir)
    toc, json_config = get_rst_toc(workspace_dir, Path(config['workspace']['rst']), exercises)
    toc, tokens = codio_transformations(toc, transformation_rules, insert_rules)
    book, metadata = make_metadata_items(config)
    chapter = None
    chapter_num = 0
    subsection_num = 0
    children_containers = [book["children"]]
    logging.debug("convert selected pages")
    refs = OrderedDict()
    label_counter = 0
    all_assessments = list()
    iframe_images = list()
    source_code_report = list()
    tag_references = prepare_figure_numbers(toc)
    for item in toc:
        if item.section_type == CHAPTER:
            subsection_num = 0
            chapter_num += 1
            slug_name = slugify(item.section_name)
            chapter = item.section_name
        else:
            subsection_num += 1
            slug_name = slugify(item.section_name, chapter=chapter)
        logging.debug("convert page {} - {}".format(slug_name, chapter_num))
        converted_md = item.markdown
        if not converted_md:
            label = get_labels(item.lines)
            if label:
                label_counter += 1
                refs[label] = {
                    'pageref': item.section_name
                }

            lines = cleanup_rst(item.lines)
            rst_converter = Rst2Markdown(
                lines,
                json_config,
                source_code,
                exercises,
                tag_references,
                workspace_dir=workspace_dir,
                chapter_num=chapter_num,
                subsection_num=subsection_num
            )
            converted_md = rst_converter.to_markdown()
            all_assessments += rst_converter.get_assessments()
            iframe_images += rst_converter.get_iframe_images()

            for code_path in rst_converter.get_source_code_paths():
                source_code_report.append(tuple([f'{chapter_num}. {chapter}', item.section_name, code_path]))

            if slug_name in tokens:
                for key, value in tokens.get(slug_name).items():
                    converted_md = converted_md.replace(key, value)

        md_path = content_dir.joinpath(slug_name + ".md")
        section, book_item = make_section_items(item, slug_name, md_path, transformation_rules, converted_md)

        if item.section_type == CHAPTER or item.codio_section == "start":
            book_item["children"] = []
            if item.section_type == CHAPTER:
                children_containers = [children_containers[0]]

        children_containers[len(children_containers) - 1].append(book_item)

        if item.codio_section == "end" and len(children_containers) > 1:
            children_containers.pop()

        if item.section_type == CHAPTER or item.codio_section == "start":
            children_containers.append(book_item["children"])

        section["files"].append({
            "path": "#tabs",
            "action": "close"
        })

        if item.exercise:
            section["files"] = make_odsa_ex_files(item.exercise_path)

        if section:
            metadata["sections"].append(section)

        write_file(md_path, converted_md)

    create_assessments_data(guides_dir, generate_dir, exercises)

    write_metadata(guides_dir, metadata, book)
    write_assessments(guides_dir, all_assessments)
    process_assets(config, generate_dir, [], [])
    process_iframe_images(config, generate_dir, iframe_images)
    print_source_code_report(source_code_report)
