import unittest
import os
import re
import functools

from pathlib import Path

from converter.toc import get_latex_toc, print_to_yaml, generate_toc, get_name


def cases(cases):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args):
            for index, c in enumerate(cases):
                new_args = args + (c if isinstance(c, tuple) else (c,))
                try:
                    f(*new_args)
                except BaseException as e:
                    print("case #{} failed, arguments {}".format(index, c))
                    raise e
        return wrapper
    return decorator


def get_file_path(name='', extension='tex'):
    dn = os.path.dirname(os.path.realpath(__file__))
    if not name:
        return os.path.join(dn, 'toc_cases')
    return os.path.join(dn, 'toc_cases/{}.{}'.format(name, extension))


def load_file(name, extension=''):
    fn = get_file_path(name, extension=extension)
    with open(fn, 'r', encoding="utf-8") as file:
        return file.read().strip('\n')


class TestSuite(unittest.TestCase):
    def test_toc_basic(self):
        path = Path(get_file_path('toc_simple'))
        toc = get_latex_toc(path.parent, path.name)
        self.assertEqual(len(toc), 6)

        should_be = [
            {'section_name': 'Computer programming', 'section_type': 'chapter', 'line_pos': 1, 'len_lines': 4},
            {'section_name': 'What is a computer?', 'section_type': 'section', 'line_pos': 5, 'len_lines': 4},
            {'section_name': 'What is programming?', 'section_type': 'section', 'line_pos': 9, 'len_lines': 4},
            {'section_name': 'Variables and operators', 'section_type': 'chapter', 'line_pos': 13, 'len_lines': 4},
            {'section_name': 'Declaring variables', 'section_type': 'section', 'line_pos': 17, 'len_lines': 4},
            {'section_name': 'Assigning variables', 'section_type': 'section', 'line_pos': 21, 'len_lines': 3}
        ]

        for i in range(len(toc)):
            item = toc[i]
            value = should_be[i]

            self.assertEqual(item.section_name, value['section_name'])
            self.assertEqual(item.section_type, value['section_type'])
            self.assertEqual(item.line_pos, value['line_pos'])
            self.assertEqual(len(item.lines), value['len_lines'])

    def test_toc_print_yaml(self):
        path = Path(get_file_path('toc_simple'))
        toc = get_latex_toc(path.parent, path.name)
        yaml = print_to_yaml(toc, path, 'tex')

        yaml = re.sub(r"directory:(.*)$", r"directory: toc_cases", yaml, flags=re.MULTILINE)
        yaml = yaml.strip()

        should_be = load_file('toc_simple', extension='yml')
        self.assertEqual(yaml, should_be)

    def test_toc_generation(self):
        path = Path(get_file_path('toc_simple'))

        generated = Path(get_file_path('codio_structure', extension='yml'))
        if generated.exists():
            generated.unlink()

        generate_toc(get_file_path(), path, ignore_exists=True)

        yaml = load_file('codio_structure', extension='yml')
        yaml = re.sub(r"directory:(.*)$", r"directory: toc_cases", yaml, flags=re.MULTILINE)
        yaml = yaml.strip()
        generated.unlink()

        should_be = load_file('toc_simple', extension='yml')
        self.assertEqual(yaml, should_be)

    def test_toc_generation_exception(self):
        with self.assertRaises(Exception):
            path = Path(get_file_path('toc_simple'))
            generate_toc(get_file_path(), path)

    @cases([
        ('\\section{Interpreting results}\\label{interpreting-results}', 'Interpreting results'),
        ('\\section{Implementing {\\tt put}}', 'Implementing put'),
        ('\\section{Profiling \\java{LinkedList} methods}', 'Profiling LinkedList methods'),
        ('\\section{Adding to the end of a \\java{LinkedList}}', 'Adding to the end of a LinkedList'),
        ('\\section{\\java{WikiFetcher}}', 'WikiFetcher'),
        ('\\section{{\\tt Comparable} and {\\tt Comparator}}', 'Comparable and Comparator')
    ])
    def test_name_generation(self, case, should_be):
        self.assertEqual(get_name(case), should_be)
