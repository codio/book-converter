import re

from converter.guides.tools import get_text_in_brackets


def _assets_extension():
    return 'pdf'


class BookDown2Markdown(object):
    def __init__(self, lines_array, chapter_num=1, figure_num=0, assets_extension=_assets_extension, refs={}):
        self._chapter_num = chapter_num
        self._figure_counter = 0
        self._figure_counter_offset = figure_num
        self.lines_array = lines_array
        self._pdfs = []
        self._refs = refs
        self.assets_extension = assets_extension
        self._figure_re = re.compile(
            r"""\\begin{figure}(.*?)(?P<block_contents>.*?)\\end{figure}""", flags=re.DOTALL + re.VERBOSE
        )
        self._figure_center_re = re.compile(
            r"""\\begin{center}(.*?)(?P<block_contents>.*?)\\end{center}""", flags=re.DOTALL + re.VERBOSE
        )
        self._includegraphics_re = re.compile(
            r"""\\includegraphics(.*?){(?P<block_contents>.*?)}""", flags=re.DOTALL + re.VERBOSE
        )

    def _figure_block(self, matchobj):
        block_contents = matchobj.group('block_contents')
        self._figure_counter += 1

        images = []
        caption = 'Figure {}.{}'.format(
            self._chapter_num, self._figure_counter + self._figure_counter_offset
        )

        for line in block_contents.strip().split("\n"):
            if "\\includegraphics" in line:
                g_lines = line.split("\\includegraphics")
                g_lines = g_lines[1:]
                for graphic in g_lines:
                    if graphic:
                        images.append(get_text_in_brackets(graphic))
            elif line.startswith("\\caption"):
                caption += get_text_in_brackets(line)

        markdown_images = []
        for image in images:
            if '.' not in image:
                ext = self.assets_extension(image)
                if ext:
                    image = '{}.{}'.format(image, ext)
            if image.lower().endswith('.pdf'):
                self._pdfs.append(image)
                image = image.replace('.pdf', '.jpg')
            markdown_images.append(
                "![{}]({})".format(caption, image)
            )

        return '{}\n\n**{}**'.format(
            '\n'.join(markdown_images),
            caption
        )

    def _includegraphics_block(self, matchobj):
        image = matchobj.group('block_contents')
        self._figure_counter += 1

        if '.' not in image:
            ext = self.assets_extension(image)
            if ext:
                image = '{}.{}'.format(image, ext)
        if image.lower().endswith('.pdf'):
            self._pdfs.append(image)
            image = image.replace('.pdf', '.jpg')

        caption = 'Figure {}.{}'.format(
            self._chapter_num, self._figure_counter + self._figure_counter_offset
        )

        return '{}\n\n**{}**\n\n'.format(
            "![{}]({})".format(caption, image), caption
        )

    def _refs_block(self, matchobj):
        ref_name = matchobj.group(1)
        if self._refs.get(ref_name):
            return self._refs.get(ref_name).get('ref')
        return matchobj.group(0)

    def _refs_remove_block(self, matchobj):
        return ''

    def _process_refs(self, output):
        ref_re = re.compile(r"""\[(.*)\](\(#.*\))?""", flags=re.MULTILINE)
        output = ref_re.sub(self._refs_block, output)
        ref_link_re = re.compile(r"""{#.*}""", flags=re.MULTILINE)
        output = ref_link_re.sub(self._refs_remove_block, output)
        ref_fig_re = re.compile(r"""\\@ref\((.*)\)""", flags=re.MULTILINE)
        output = ref_fig_re.sub(self._refs_block, output)
        return output

    def _to_markdown(self):
        output = '\n'.join(self.lines_array)
        output = self._figure_re.sub(self._figure_block, output)
        output = self._figure_center_re.sub(self._figure_block, output)
        output = self._includegraphics_re.sub(self._includegraphics_block, output)
        output = self._process_refs(output)
        return output

    def to_markdown(self):
        return self._to_markdown()

    def get_figure_counter(self):
        return self._figure_counter

    def get_pdfs_for_convert(self):
        return self._pdfs
