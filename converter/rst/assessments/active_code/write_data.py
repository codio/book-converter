import logging
import shutil
from pathlib import Path

from converter.guides.tools import write_file


def create_active_code_files(guides_dir, exercises):
    if not exercises:
        return
    logging.debug('process create active code test assessments data')

    tests_dir = guides_dir.joinpath('secure/active_code')
    tests_dir.mkdir(exist_ok=True, parents=True)

    lib_dir = guides_dir.joinpath(f'code')
    lib_dir.mkdir(exist_ok=True, parents=True)
    source_lib_path = Path('converter/rst/assessments/active_code/CodeTestHelper.java')
    shutil.copy(source_lib_path, lib_dir)

    for exercise in exercises:
        options = exercise.options
        exercise_name = exercise.name
        class_name = options.get('class_name', '')
        test_class_name = options.get('test_class_name', '')
        class_code = options.get('code', '')
        tests_code = options.get('tests', '')

        private_exercise_dir = tests_dir.joinpath(exercise_name)
        private_exercise_dir.mkdir(exist_ok=True, parents=True)
        test_file = private_exercise_dir.joinpath(f'{test_class_name}.java')

        code_dir = guides_dir.joinpath(f'code/{exercise_name}')
        code_dir.mkdir(exist_ok=True, parents=True)
        code_file = code_dir.joinpath(f'{class_name}.java')

        write_file(code_file, class_code)
        write_file(test_file, tests_code)
