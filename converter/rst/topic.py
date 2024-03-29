import re


class Topic(object):
    def __init__(self, source_string, caret_token):
        self.str = source_string
        self._caret_token = caret_token
        self._topic_re = re.compile(
            r"""(\.\.[ ]_(?P<tag>.*?):\n\s*)?^\.{2}[ ]topic::[ ]:figure_number:(?P<figure_number>[0-9.]*):?[ ]+
                (?P<type>.*?)\n\n*(?P<content>(?:\s+[^\n]+\n*)*)""",
            flags=re.MULTILINE + re.VERBOSE)

    def _topic(self, matchobj):
        caret_token = self._caret_token
        topic_type = matchobj.group('type')
        content = matchobj.group('content')
        content = re.sub(r"\n +", "\n ", content)

        figure_number = matchobj.group('figure_number') if matchobj.group('figure_number') is not None else ''

        return f'\n<div style="padding: 20px; border: 1px; border-style: solid; border-color: silver;">' \
               f'{caret_token}{caret_token}**{topic_type} {figure_number}**<br/>' \
               f'{caret_token}{caret_token}\n\n{content}\n\n</div><br/>{caret_token}{caret_token}\n'

    def convert(self):
        output = self.str
        output = self._topic_re.sub(self._topic, output)
        return output
