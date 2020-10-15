import yaml
import re

from collections import OrderedDict
from pathlib import Path

from converter.convert import get_latex_toc
from converter.guides.item import CHAPTER


def ordered_dump(data, stream=None, **kwds):
    class OrderedDumper(yaml.SafeDumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, data.items())

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


def ref_dict(config):
    toc = get_latex_toc(Path(config['workspace']['directory']), Path(config['workspace']['tex']))
    refs = make_refs(toc)

    out = {'refs': {'chapter_counter_from': 0, 'overrides': refs}}

    print(ordered_dump(out, default_flow_style=False))


def get_ref_chapter_counter_from(config):
    ref_section = config.get('refs')
    if not ref_section:
        return 1

    chapter_counter_from = ref_section.get('chapter_counter_from', 1)
    if not isinstance(chapter_counter_from, int):
        return 1

    return chapter_counter_from


def override_refs(refs, config):
    ref_section = config.get('refs')
    if not ref_section:
        return refs

    ref_overriders = ref_section.get('overrides')
    if not ref_overriders:
        return refs

    return {**refs, **ref_overriders}


def make_bookdown_refs(config):
    return config.get('refs', {}).get('overrides', {})


def make_refs(toc, chapter_counter_from=1):
    refs = OrderedDict()
    chapter_counter = None
    section_counter = 0
    exercise_counter = 0
    figs_counter = 0
    is_figure = False
    is_exercise = False
    line_break = False

    for item in toc:
        if item.section_type == CHAPTER:
            if chapter_counter is None:
                chapter_counter = chapter_counter_from
            else:
                chapter_counter += 1
            section_counter = 0
            figs_counter = 0
            exercise_counter = 0
        else:
            section_counter += 1
        for line in item.lines:
            if line.startswith("\\sectionfile"):
                result = re.search(r"\\sectionfile(\[.*?\])?{(?P<block_name>.*?)}{(?P<block_path>.*?)}", line)
                label = result.group("block_path")
                if label:
                    refs[label] = {
                        'pageref': item.section_name
                    }
                    refs[label]["ref"] = f'{chapter_counter}.{section_counter}'
            if line.startswith("\\begin{figure}"):
                figs_counter += 1
                is_figure = True
            elif line.startswith("\\end{figure}"):
                is_figure = False
            elif line.startswith("\\begin{exercise}"):
                exercise_counter += 1
                is_exercise = True
            elif line.startswith("\\end{exercise}"):
                is_exercise = False
            elif "figure{" in line or "figure[" in line:
                result = re.search(r'\\(?P<block_name>pic|table|codefile)figure(\[.*\])?{(?P<path>.*?)}'
                                   r'(%?\s*)?({(?P<ref>.*?)})?', line)
                if result:
                    ref = result.group('ref')
                    if ref:
                        figs_counter += 1
                        refs[ref] = {
                            'pageref': item.section_name
                        }
                        refs[ref]["ref"] = f'{chapter_counter}.{figs_counter}'
                    else:
                        line_break = True
                        continue
            elif line_break:
                res = re.search(r'{(?P<ref>fig:.*?)}', line)
                if res:
                    ref = res.group('ref')
                    figs_counter += 1
                    refs[ref] = {
                        'pageref': item.section_name
                    }
                    refs[ref]["ref"] = f'{chapter_counter}.{figs_counter}'
                    line_break = False
            elif "\\begin{enumerate}" in line:
                items_counter = 0
                for ln in item.lines:
                    if "\\item" in ln:
                        items_counter += 1
                        result = re.search(r'\\item\\label{(?P<ref>item:.*?)}', ln)
                        if result:
                            ref = result.group('ref')
                            refs[ref] = {
                                'item_num': items_counter
                            }
                    if "\\end{enumerate}" in ln:
                        items_counter = 0
            elif "\\label{" in line and not line.startswith("\\item"):
                start_pos = line.find("\\label{")
                end_pos = line.find("}", start_pos)
                label = line[start_pos + 7:end_pos]
                refs[label] = {
                    'pageref': item.section_name
                }
                if is_figure:
                    refs[label]["ref"] = '{}.{}'.format(chapter_counter, figs_counter)
                elif is_exercise:
                    refs[label]["ref"] = '{}.{}'.format(chapter_counter, exercise_counter)
                elif item.section_type == CHAPTER:
                    refs[label]["ref"] = '{}'.format(chapter_counter)
                else:
                    refs[label]["ref"] = '{}.{}'.format(chapter_counter, section_counter)

    return refs
