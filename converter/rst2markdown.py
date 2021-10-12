import pathlib
import re
import uuid

from converter.rst.assessments.active_code.activecode import ActiveCode
from converter.rst.assessments.fib import FillInTheBlanks
from converter.rst.assessments.free_text import FreeText
from converter.rst.assessments.mchoice import MultiChoice
from converter.rst.assessments.parsons import Parsons
from converter.rst.assessments.tabbed import Tabbed
from converter.rst.assessments.timed import Timed
from converter.rst.avembed import AvEmbed
from converter.rst.bibliography import Bibliography
from converter.rst.code_block import CodeBlock
from converter.rst.code_include import CodeInclude
from converter.rst.comment import Comment
from converter.rst.definition import Definition
from converter.rst.epigraph import Epigraph
from converter.rst.external_link import ExternalLink
from converter.rst.extrtoolembed import ExtrToolEmbed
from converter.rst.footnote import Footnote
from converter.rst.glossary import Glossary
from converter.rst.heading import Heading
from converter.rst.image import Image
from converter.rst.image2 import Image2
from converter.rst.image2directive import Image2Directives
from converter.rst.indented_code import IndentedCode
from converter.rst.ignore import Ignore
from converter.rst.inlineav import InlineAv
from converter.rst.line_block import LineBlock
from converter.rst.note import Note
from converter.rst.numref import Numref
from converter.rst.list import List
from converter.rst.math import Math
from converter.rst.math_block import MathBlock
from converter.rst.only import Only
from converter.rst.paragraph import Paragraph
from converter.rst.raw_html_directives import RawHtmlDirectives
from converter.rst.raw_html_tag import RawHtmlTag
from converter.rst.ref import Ref
from converter.rst.sidebar import Sidebar
from converter.rst.slide import Slide
from converter.rst.table import Table
from converter.rst.term import Term
from converter.rst.tip import Tip
from converter.rst.todo_block import TodoBlock
from converter.rst.topic import Topic
from converter.rst.simple_table import SimpleTable
from converter.rst.tag_reference import TagReference
from converter.rst.preparer_math_block import PreparerMathBlock
from converter.rst.character import Character
from converter.rst.youtube import Youtube

OPEN_DSA_CDN = 'https://global.codio.com/opendsa/v6'


class Rst2Markdown(object):
    def __init__(self,
                 lines_array,
                 tag_directives,
                 exercises={},
                 source_code_dir=None,
                 source_code_type='java',
                 tag_references=None,
                 workspace_dir=pathlib.Path('.'),
                 chapter_num=0,
                 subsection_num=0):
        self._caret_token = str(uuid.uuid4())
        self._math_block_separator_token = str(uuid.uuid4())
        self._chapter_num = chapter_num
        self._subsection_num = subsection_num
        self._tag_directives = tag_directives
        self._assessments = list()
        self._iframe_images = list()
        self.lines_array = lines_array
        self._exercises = exercises
        self._tag_references = tag_references
        self.workspace_dir = workspace_dir
        self.source_code_dir = source_code_dir
        self.source_code_type = source_code_type
        self._source_code_paths = list()

    def _enum_lists_parse(self, lines):
        counter = 0
        list_flag = False
        for ind, line in enumerate(lines):
            next_line = lines[ind + 1] if ind + 1 < len(lines) else ''
            if self.bullet_match(line):
                list_flag = True
                counter += 1
                lines[ind] = line.replace("#", str(counter), 1)
            if next_line[:1].strip() and not self.bullet_match(next_line) and list_flag:
                list_flag = False
                counter = 0
        return lines

    @staticmethod
    def bullet_match(line):
        return re.search(r'^ *[(]?#[.|)] ', line)

    @staticmethod
    def load_file(path):
        with open(path, 'r') as file:
            return file.readlines()

    def get_assessments(self):
        return self._assessments

    def get_iframe_images(self):
        return self._iframe_images

    def get_source_code_paths(self):
        return self._source_code_paths

    def to_markdown(self):
        self.lines_array = self._enum_lists_parse(self.lines_array)
        lines_array = PreparerMathBlock(self.lines_array, self._math_block_separator_token).prepare()
        output = '\n'.join(lines_array) + '\n\n>>>'
        output = re.sub(r'\|---\|', '--', output)
        output = re.sub(r'^\|$', '<br/>', output, flags=re.MULTILINE)
        output = re.sub(r'^- >', r'- \\>', output, flags=re.MULTILINE)
        output = re.sub(r'C\+\+', 'C\\+\\+', output)
        output = Ignore(output).convert()
        output = Timed(output, self._caret_token).convert()
        output = Slide(output, self._caret_token).convert()
        output = Tabbed(output, self._caret_token).convert()
        output, html_tags = RawHtmlDirectives(output, self._caret_token).convert()
        output = RawHtmlTag(output, html_tags, self._caret_token).convert()
        output, assessments = MultiChoice(output, self._caret_token).convert()
        if assessments:
            self._assessments.extend(assessments)
        output, assessments = FillInTheBlanks(output, self._caret_token).convert()
        if assessments:
            self._assessments.extend(assessments)
        output, assessments = FreeText(output, self._caret_token).convert()
        if assessments:
            self._assessments.extend(assessments)
        output, assessments = Parsons(output, self._caret_token).convert()
        if assessments:
            self._assessments.extend(assessments)
        output, assessments = ActiveCode(output, self._caret_token).convert()
        if assessments:
            self._assessments.extend(assessments)
        output = CodeBlock(output, self._caret_token).convert()
        output = Youtube(output, self._caret_token).convert()
        output, images = Image2Directives(output).convert()
        if images:
            self._tag_directives.extend(images)
        output = Image2(output, self._tag_directives, self._caret_token).convert()
        output = Note(output, self._caret_token).convert()
        output = TagReference(output, self._tag_references).convert()
        output = MathBlock(output, self._caret_token, self._math_block_separator_token).convert()
        output, assessments = ExtrToolEmbed(output, self._exercises).convert()
        if assessments:
            self._assessments.extend(assessments)
        output = Footnote(output, self._caret_token).convert()
        output = Heading(output, self._caret_token).convert()
        output = TodoBlock(output).convert()
        output = Topic(output, self._caret_token).convert()
        output = Tip(output, self._caret_token).convert()
        output = Image(output, self._caret_token, OPEN_DSA_CDN).convert()
        output, iframe_images = InlineAv(output, self._caret_token, self.workspace_dir, OPEN_DSA_CDN).convert()
        if iframe_images:
            self._iframe_images.extend(iframe_images)
        output, assessments = AvEmbed(output, self._caret_token, OPEN_DSA_CDN, self.workspace_dir).convert()
        if assessments:
            self._assessments.extend(assessments)
        output = Ref(output).convert()
        output = Numref(output).convert()
        output = Term(output).convert()
        output = SimpleTable(output, self._caret_token).convert()
        output = Table(output, self._caret_token).convert()
        output = Epigraph(output, self._caret_token).convert()
        output = Sidebar(output, self._caret_token).convert()
        output = ExternalLink(output).convert()
        output = Only(output).convert()
        output = IndentedCode(output, self._caret_token).convert()
        output, source_code_paths = CodeInclude(
            output,
            self._caret_token,
            self.workspace_dir,
            self.load_file,
            self.source_code_dir,
            self.source_code_type
        ).convert()
        if source_code_paths:
            self._source_code_paths.extend(source_code_paths)
        output = Glossary(output, self._caret_token).convert()
        output = Bibliography(output, self._caret_token).convert()
        output = LineBlock(output, self._caret_token).convert()
        output = Definition(output, self._caret_token).convert()
        output = Character(output).convert()
        # Comment before Paragraph
        output = Comment(output).convert()
        output = Paragraph(output).convert()
        output = List(output).convert()
        output = Math(output).convert()
        output = re.sub(r'>>>', '', output)
        output = re.sub(self._caret_token, "\n", output)
        return output
