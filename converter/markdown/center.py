import re

from converter.markdown.text_as_paragraph import TextAsParagraph

center_re = re.compile(r"""\\begin{center}(?P<block_contents>.*?)\\end{center}""", flags=re.DOTALL + re.VERBOSE)


class Center(TextAsParagraph):
    def __init__(self, latex_str, caret_token):
        super().__init__(latex_str, caret_token)

    def make_block(self, matchobj):
        block_contents = matchobj.group('block_contents')
        block_contents = self.to_paragraph(block_contents)
        block_contents = block_contents.replace("\\\\", "<br/>")
        caret_token = self._caret_token
        return f'{caret_token}<center>{caret_token}{block_contents}{caret_token}</center>'

    def convert(self):
        return center_re.sub(self.make_block, self.str)
