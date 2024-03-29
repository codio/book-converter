import pathlib
import yaml
import re

from pathlib import Path

from converter.guides.item import SectionItem, SECTION, CHAPTER
from converter.guides.tools import write_file, get_text_in_brackets
from converter.loader import load_json_file


def is_section(line):
    return line.startswith('\\section')


def is_chapter(line):
    return line.startswith('\\chapter')


def is_toc(line):
    return is_section(line) or is_chapter(line)


def is_input(line):
    line = line.lstrip()
    return line.startswith('\\input')


def is_include(line):
    line = line.lstrip()
    return line.startswith('\\include')


def input_file(line):
    return get_text_in_brackets(line)


def include_file(line):
    return get_text_in_brackets(line)


def cleanup_name(name):
    l_pos = name.find('{')
    r_pos = name.find('}')
    cut_pos = l_pos + 1
    if l_pos != -1 and r_pos != -1 and l_pos < r_pos:
        if name[l_pos + 1] == '\\':
            cut_pos = name.find(' ', l_pos)
        else:
            for pos in range(l_pos, -1, -1):
                if name[pos] == '\\':
                    l_pos = pos + 1
                    break
        if l_pos != 0:
            l_pos = l_pos - 1
        else:
            cut_pos += 1
        res = name[0:l_pos] + name[cut_pos:r_pos] + name[r_pos + 1:]
        return cleanup_name(res)
    return name


def get_name(line):
    level = 0
    start = 0
    end = len(line)
    for pos, ch in enumerate(line):
        if ch == '{':
            if start == 0:
                start = pos
            else:
                level += 1
        elif ch == '}':
            if level == 0:
                end = pos
                break
            else:
                level -= 1
    return cleanup_name(line[start + 1:end])


def get_bookdown_name(line):
    name = line[line.index(' ') + 1:].strip()
    if '{' in name and name.endswith('}'):
        name = name[0:name.rfind('{') - 1]
        name = name.strip()
    return name


def is_section_file(line):
    return line.strip().startswith("\\sectionfile")


def get_section_lines(line, tex_folder):
    section_line_re = re.compile(r"""\\sectionfile{(?P<block_name>.*?)}{(?P<block_path>.*?)}""")
    result = section_line_re.search(line)
    if result:
        file = result.group("block_path")
        if '.tex' not in file:
            file = '_{}.tex'.format(file)
        tex_file = tex_folder.joinpath(file)
        if tex_file.exists():
            with open(tex_file, 'r', errors='replace') as file:
                return file.readlines()

    return []


def process_toc_lines(lines, tex_folder, parent_folder):
    toc = []
    line_pos = 1
    item_lines = []
    for line in lines:
        line = line.rstrip('\r\n')
        if is_toc(line):
            if toc:
                if item_lines:
                    toc[len(toc) - 1].lines = item_lines
                item_lines = []
            section_type = CHAPTER if is_chapter(line) else SECTION
            toc.append(SectionItem(section_name=get_name(line), section_type=section_type, line_pos=line_pos))
            if is_section_file(line):
                section_lines = get_section_lines(line, parent_folder)
                for sub_line in section_lines:
                    item_lines.append(sub_line.rstrip('\n'))
        elif is_input(line) or is_include(line):
            if is_input(line):
                sub_toc = get_latex_toc(tex_folder, input_file(line))
            else:
                sub_toc = get_latex_toc(tex_folder, include_file(line))
            if sub_toc:
                toc = toc + sub_toc
            else:
                r_file = input_file(line) if is_input(line) else include_file(line)
                sub_content = get_include_lines(tex_folder, r_file)
                if sub_content:
                    item_lines.extend(sub_content)
                    line_pos += len(sub_content)
                    continue

        line_pos += 1
        if toc:
            item_lines.append(line)
    if toc and item_lines and not toc[len(toc) - 1].lines:
        toc[len(toc) - 1].lines = item_lines
    return toc


def get_include_lines(tex_folder, tex_name):
    a_path = tex_folder.joinpath(tex_name).resolve()
    if not str(a_path).endswith(".tex"):
        a_path = tex_folder.joinpath("{}.tex".format(tex_name)).resolve()
    if not a_path.exists():
        return None
    with open(a_path, 'r', errors='replace') as file:
        return file.readlines()


def get_latex_toc(tex_folder, tex_name):
    lines = get_include_lines(tex_folder, tex_name)
    if not lines:
        return None
    a_path = tex_folder.joinpath(tex_name).resolve()
    return process_toc_lines(lines, tex_folder, a_path.parent)


def process_bookdown_lines(lines, name_without_ext):
    toc = []
    item_lines = []
    line_pos = 1
    quotes = False
    for line in lines:
        line = line.rstrip('\r\n')
        if '\\begin' in line:
            line = line.strip()
        if '```' in line:
            line = line.strip()
            quotes = not quotes
        top_level = not quotes and (line.startswith('# ') or line.startswith('## '))
        if top_level:
            if toc:
                if item_lines:
                    toc[len(toc) - 1].lines = item_lines
                item_lines = []
            section_type = CHAPTER if line.startswith('# ') else SECTION
            toc.append(SectionItem(
                section_name="{}----{}".format(name_without_ext, get_bookdown_name(line)),
                section_type=section_type,
                line_pos=line_pos)
            )
        if toc:
            item_lines.append(line)
        line_pos += 1
    if toc and item_lines and not toc[len(toc) - 1].lines:
        toc[len(toc) - 1].lines = item_lines
    return toc


def process_bookdown_file(folder, name, name_without_ext):
    a_path = folder.joinpath(name).resolve()
    with open(a_path, 'r', errors='replace') as file:
        lines = file.readlines()
        return process_bookdown_lines(lines, name_without_ext)


def get_bookdown_toc(folder, name):
    a_path = folder.joinpath(name).resolve()
    with open(a_path, 'r', errors='replace') as stream:
        content = yaml.load(stream, Loader=yaml.FullLoader)
        rmd_files = content.get('rmd_files')
        toc = []
        for file in rmd_files:
            name_without_ext = Path(file).stem
            toc += process_bookdown_file(folder.joinpath('_book'), "{}.md".format(name_without_ext), name_without_ext)
        return toc


def get_rst_toc(workspace_dir, json_config_name, exercises={}):
    toc = []
    source_path = workspace_dir.joinpath('RST/en').resolve()
    json_config_dir = workspace_dir.joinpath('config')
    json_config_path = json_config_dir.joinpath(json_config_name).resolve()
    json_config = load_json_file(json_config_path)
    chapters = json_config.get('chapters')
    for chapter in chapters:
        pages = chapters.get(chapter).keys()
        toc.append(SectionItem(
            section_name=chapter,
            section_type='chapter',
            line_pos=0)
        )
        for page in pages:
            rst_file_name = f'{page}.rst'
            rst_file_path = pathlib.Path(source_path.joinpath(rst_file_name).resolve())
            if not rst_file_path.exists():
                print("File %s doesn't exist\n" % rst_file_name)
                continue
            toc += process_rst_file(rst_file_path, exercises)
    return toc, json_config


def _math(matchobj):
    content = matchobj.group('content')
    content = content.replace("\\", "")
    return f'{content}'


def process_rst_file(path, exercises):
    with open(path, 'r', errors='replace') as file:
        lines = file.readlines()
        return process_rst_lines(lines, exercises)


def process_rst_lines(lines, exercises):
    toc = []
    item_lines = []
    contains_exercises = False
    for ind, line in enumerate(lines):
        line = line.rstrip('\r\n')
        next_line = lines[ind + 1] if ind + 1 < len(lines) else ''
        next_line = next_line.strip()
        is_chapter = next_line == "=" * len(line)
        if next_line.startswith("===") and is_chapter:
            section_name = line.replace("\\", "\\\\")
            section_name = re.compile(r""":math:`(?P<content>.*?)`""").sub(_math, section_name)
            toc.append(SectionItem(
                section_name=section_name,
                section_type="section",
                line_pos=0)
            )
            item_lines = []
        if line.startswith(".. extrtoolembed::"):
            result = re.match(r'\.\. extrtoolembed:: \'(?P<name>.*?)\'', line)
            if result:
                contains_exercises = True
                ex_name = result.group('name')
                section_name = f'Exercise: {ex_name}'
                exercise = exercises.get(ex_name.lower(), {})
                exercise_path = exercise.get('ex_path', '')
                toc.append(SectionItem(
                    section_name=section_name,
                    section_type="section",
                    exercise=True,
                    exercise_path=exercise_path,
                    line_pos=0)
                )
                content = f'{{Check It!|assessment}}(test-{ex_name.lower()})'
                toc[len(toc) - 1].lines.append(content)
        item_lines.append(line)
    if toc and item_lines and not toc[0].lines:
        item_lines.append('')
        toc[0].lines = item_lines
        toc[0].contains_exercises = contains_exercises
    return toc


def print_to_yaml(structure, tex, data_format):
    directory = tex.parent.parent.resolve() if data_format == 'rst' else tex.parent.resolve()
    yaml_structure = """workspace:
  directory: {}
  {}: {}
assets:
sections:
""".format(directory, data_format, tex.name)
    first_item = True
    exercises_flag = False
    for ind, item in enumerate(structure):
        yaml_structure += "  - name: \"{}\"\n    type: {}\n".format(item.section_name, item.section_type)

        next_item = structure[ind + 1] if ind + 1 < len(structure) else {}
        prev_item = structure[ind - 1]

        if exercises_flag and not prev_item.exercise:
            yaml_structure += "    configuration:\n" \
                              "      layout: 2-panels\n"
        elif prev_item.exercise and not item.exercise:
            yaml_structure += "    configuration:\n" \
                              "      layout: 1-panel\n"

        if item.contains_exercises:
            yaml_structure += "    codio_section: start\n"
            exercises_flag = True
        elif exercises_flag and not next_item.exercise:
            yaml_structure += "    codio_section: end\n"
            exercises_flag = False

        if first_item:
            first_item = False
            yaml_structure += "    configuration:\n      layout: 1-panel\n"
    return yaml_structure


def generate_toc(file_path, structure_path, ignore_exists=False):
    path = Path(file_path)
    if path.exists() and not ignore_exists:
        raise Exception("Path exists")
    tex = Path(structure_path)
    bookdown = str(structure_path).endswith('_bookdown.yml')
    rst = str(structure_path).endswith('.json')
    if bookdown:
        toc = get_bookdown_toc(tex, tex.name)
        data_format = 'bookdown'
    elif rst:
        toc, json_config = get_rst_toc(tex.parent.parent, tex.name)
        data_format = 'rst'
    else:
        toc = get_latex_toc(tex.parent, tex.name)
        data_format = 'tex'
    path.mkdir(parents=True, exist_ok=ignore_exists)

    content = print_to_yaml(toc, tex, data_format)
    a_path = path.joinpath("codio_structure.yml").resolve()
    write_file(a_path, content)
