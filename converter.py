import logging
from argparse import ArgumentParser

from converter.toc import generate_toc
from converter.loader import load_config_file
from converter.convert import convert

if __name__ == '__main__':
    parser = ArgumentParser(description='Process latex to codio guides.')
    parser.add_argument('paths', metavar='PATH', type=str, nargs='+', help='path to a book config')
    parser.add_argument('--generate', type=str, help='path to a latex book')
    parser.add_argument('-l', '--log', action='store', default=None)

    args = parser.parse_args()

    logging.basicConfig(filename=args.log, level=logging.DEBUG,
                        format='[%(asctime)s] %(levelname).5s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')

    if args.generate:
        generate_toc(args.paths[0], args.generate)
    else:
        for path in args.paths:
            config, base_path = load_config_file(path)
            convert(config, base_path)
