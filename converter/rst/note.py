import re


class Note(object):
    def __init__(self, source_string, caret_token):
        self.str = source_string
        self._caret_token = caret_token
        self._note_re = re.compile(r"""^( *\.\.\snote::.*?\n)(?P<content>.*?)\n(?=\S)""",
                                   flags=re.MULTILINE + re.DOTALL)

    def _note(self, matchobj):
        caret_token = self._caret_token
        content = matchobj.group('content').strip()
        return f'{caret_token}||| info{caret_token}{content}{caret_token}|||{caret_token}{caret_token}\n'

    def convert(self):
        output = self._note_re.sub(self._note, self.str)
        return output