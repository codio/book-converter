import re
import uuid

from collections import namedtuple

from converter.markdown.text_as_paragraph import TextAsParagraph

Code = namedtuple('Code', ['name', 'source'])

code_re = re.compile(r"""\\codefilefigure(\[(?P<guid>.*?)])?{(?P<file_path>.*?)}(?P<fuck>.*?){(?P<label>.*?)}""",
                     flags=re.DOTALL + re.VERBOSE)


class CodeFigure(TextAsParagraph):
    def __init__(self, latex_str, caret_token, percent_token, load_workspace_file):
        super().__init__(latex_str, caret_token)
        self._load_file = load_workspace_file
        self._percent_token = percent_token
        self._matches = []
        self._source_codes = []

    def make_block(self, matchobj):
        file_path = matchobj.group('file_path')
        file_content = self._load_file(file_path)
        caret_token = self._caret_token
        replace_token = str(uuid.uuid4())

        self._matches.append(replace_token)

        if not file_content:
            return replace_token

        self._source_codes.append(Code(file_path, file_content))

        file_content = re.sub(r"%", self._percent_token, file_content)
        file_content = re.sub(r"\n", self._caret_token, file_content)

        return f'{caret_token}**source:{file_path}**{caret_token}' \
            f'```code{caret_token}{file_content}{caret_token}```{caret_token}{replace_token}'

    def remove_matched_token(self, output, chars):
        pos = output.find(chars)
        br_pos = output.find('{', pos) + 1
        token_len = br_pos - pos

        if pos == -1:
            return output
        level = 0
        for index in range(pos + token_len, len(output), 1):
            ch = output[index]
            if ch == '}':
                if level == 0:
                    output = output[0:pos] + output[pos + token_len:index - 1] + output[index + 1:]
                    break
                else:
                    level += 1
            elif ch == '{':
                level -= 1
        return output

    def convert(self):
        output = self.str

        output = code_re.sub(self.make_block, output)

        for token in self._matches:
            output = self.remove_matched_token(output, token)

        return output, self._source_codes
