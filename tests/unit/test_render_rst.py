import pathlib
import unittest
import os

from collections import OrderedDict

from converter.rst2markdown import Rst2Markdown
from converter.guides.tools import write_file


def write_md_case(name, content):
    dn = os.path.dirname(os.path.realpath(__file__))
    fn = os.path.join(dn, 'cases_rst/{}.md'.format(name))
    write_file(fn, content)


def load_file(path):
    dn = os.path.dirname(os.path.realpath(__file__))
    fn = os.path.join(dn, path)
    with open(fn, 'r') as file:
        return file.read()


def load_rst(path):
    return load_file('{}.rst'.format(path))


def load_md(path):
    return load_file('{}.md'.format(path)).rstrip('\n')


def make_converter(path):
    return Rst2Markdown(load_rst(path).split('\n'), {'code_dir': 'SourceCode'}, 'java', OrderedDict())


class TestSuite(unittest.TestCase):
    def write_md(self, name):
        path = "cases_rst/{}".format(name)
        converter = make_converter(path)
        write_md_case(name, converter.to_markdown())

    def run_case(self, name, custom_workspace_dir=None):
        path = "cases_rst/{}".format(name)
        converter = make_converter(path)
        if custom_workspace_dir:
            converter.workspace_dir = custom_workspace_dir
        self.assertEqual(load_md(path), converter.to_markdown().rstrip('\n'))

    def test_avembed_render(self):
        self.run_case("avembed")

    def test_inlineav_render(self):
        self.run_case("inlineav")
        converter = make_converter("cases_rst/{}".format("inlineav"))
        converter.to_markdown()
        js_av_images = converter.get_iframe_images()
        self.assertEqual(len(js_av_images), 1)
        self.assertTrue('chomskycon' in js_av_images[0].src.lower())
        self.assertTrue('chomskycon' in js_av_images[0].path.lower())
        self.assertTrue('chomskycon' in js_av_images[0].content.lower())

    def test_table_render(self):
        self.run_case("table")

    def test_simple_table_render(self):
        self.run_case("simple_table")

    def test_external_link_render(self):
        self.run_case("external_link")

    def test_sidebar_render(self):
        self.run_case('sidebar')

    def test_image_render(self):
        self.run_case('image')

    def test_footnote_render(self):
        self.run_case('footnote')

    def test_bibliography_render(self):
        self.run_case('bibliography')

    def test_code_include_render(self):
        self.run_case('code_include', pathlib.Path.cwd().joinpath('./tests/unit/cases_rst'))

    def test_glossary_render(self):
        self.run_case('glossary')

    def test_heading_render(self):
        self.run_case('heading')

    def test_topic_render(self):
        self.run_case('topic')

    def test_tip_render(self):
        self.run_case('tip')

    def test_math_render(self):
        self.run_case('math')

    def test_only_render(self):
        self.run_case('only')

    def test_ref_render(self):
        self.run_case('ref')

    def test_term_render(self):
        self.run_case('term')

    def test_epigraph_render(self):
        self.run_case('epigraph')
