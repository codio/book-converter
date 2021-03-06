import re


class Italic(object):
    def __init__(self, latex_str):
        self.str = latex_str

    def convert(self):
        output = self.str
        output = re.sub(r"\\emph{(.*?)}", r"*\1*", output, flags=re.DOTALL + re.VERBOSE)
        output = re.sub(r"{\\em[ ](.*?)}", r"*\1*", output, flags=re.DOTALL + re.VERBOSE)
        output = re.sub(r"{\\it[ ](.*?)}", r"*\1*", output, flags=re.DOTALL + re.VERBOSE)

        return output
