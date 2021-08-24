import re

from converter.rst.assesments.assessment_const import DEFAULT_POINTS, MULTIPLE_CHOICE
from converter.rst.model.assessment_data import AssessmentData


class MultiChoice(object):
    def __init__(self, source_string, caret_token):
        self.str = source_string
        self._caret_token = caret_token
        self._assessments = list()
        self._mchoice_re = re.compile(r"""^( *\.\.\smchoice:: (?P<name>.*?)\n)(?P<options>.*?)\n(?=\S|(?!^$)$)""",
                                      flags=re.MULTILINE + re.DOTALL)
        self._clickablearea_re = re.compile(
            r"""^( *\.\.\sclickablearea:: (?P<name>.*?)\n)(?P<options>.*?)\n(?=\S|(?!^$)$)""",
            flags=re.MULTILINE + re.DOTALL)

    def _mchoice(self, matchobj):
        options = {}
        caret_token = self._caret_token
        name = matchobj.group('name')
        options_group = matchobj.group('options')
        option_re = re.compile(':([^:]+): (.+)')
        options_group_list = options_group.split('\n')
        for line in options_group.split('\n'):
            opt_match = option_re.match(line.strip())
            if opt_match:
                options_group_list.pop(opt_match.pos)
                options[opt_match[1]] = opt_match[2]

        question = [item.strip() for item in options_group_list if item != '']
        if question:
            options['question'] = question[0]

        options['multipleResponse'] = False
        assessment_id = f'multiple-choice-{name.lower()}'
        self._assessments.append(AssessmentData(assessment_id, name, MULTIPLE_CHOICE, DEFAULT_POINTS, options))

        return f'{caret_token}{{Check It!|assessment}}({assessment_id}){caret_token}\n'

    def _clickablearea(self, matchobj):
        options = {}
        caret_token = self._caret_token
        name = matchobj.group('name')
        options_group = matchobj.group('options')
        option_re = re.compile(':([^:]+):(?: (.+))?')
        options_group_list = options_group.split('\n')
        for line in options_group.split('\n'):
            if line.strip() == '':
                break
            opt_match = option_re.match(line.strip())
            if opt_match:
                options_group_list.pop(opt_match.pos)
                options[opt_match[1]] = opt_match[2]

        answers = '\n'.join(options_group_list)
        answers_match = re.finditer('^(?P<space> +):click-(?P<correct>correct|incorrect):(?P<text>.*?):endclick:',
                                    answers, flags=re.MULTILINE)
        if answers_match:
            answers = []
            for item in answers_match:
                is_correct = item.group('correct') == 'correct'
                answer = item.group('space') + item.group('text')
                answers.append({'is_correct': is_correct, 'answer': answer})
            options['answers'] = answers

        options['multipleResponse'] = True
        assessment_id = f'multiple-choice-{name.lower()}'
        self._assessments.append(AssessmentData(assessment_id, name, MULTIPLE_CHOICE, DEFAULT_POINTS, options))

        return f'{caret_token}{{Check It!|assessment}}({assessment_id}){caret_token}\n'

    def convert(self):
        output = self.str
        output = self._mchoice_re.sub(self._mchoice, output)
        output = self._clickablearea_re.sub(self._clickablearea, output)
        return output, self._assessments
