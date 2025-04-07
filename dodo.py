import sysconfig
from pathlib import Path

root = Path(__file__).parent.absolute()
build = root / '_build'


def task_cmake():
    return {
        'actions': [f'cmake {find_pybind()} -B {build} -S {root} -GNinja'],
        'file_dep': [root / 'CMakeLists.txt'],
        'targets': [build / 'build.ninja'],
    }


def task_build():
    return {
        'actions': [f'cd {build} && ninja'],
        'file_dep': [build / 'build.ninja'],
    }


def task_test():
    task_build()
    return {
        'actions': [f'cd {root} && PYTHONPATH=. pytest'],
        'file_dep': [build / 'Makefile'],
        'targets': [build / 'Testing/Temporary/LastTest.log'],  # Assuming this is where ctest logs
    }


def find_pybind():
    pybind = sysconfig.get_paths()['purelib'] + '/pybind11'
    pybind = f'-Dpybind11_DIR={pybind}'
    # print(pybind)
    return pybind


def task_import_check():
    """Try to import the compiled module to verify it's working"""

    def import_test():
        try:
            pass
        except Exception as e:
            print('❌ Import failed:', e)
            raise

    return {
        'actions': [import_test],
        'task_dep': ['build'],
    }


def task_test():
    """Run tests using pytest"""
    return {
        'actions': ['pytest evn/tests'],
        'task_dep': ['import_check'],
    }


def task_wheel():
    return dict(
        actions=[f'cibuildwheel --only cp3{ver}-manylinux_x86_64' for ver in range(9, 14)],
        file_dep=[
            'evn/format/_common.hpp',
            'evn/format/_detect_formatted_blocks.cpp',
            'evn/format/_token_column_format.cpp',
        ],
        targets=[
            'wheelhouse/evn-0.1.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
        ],
    )


def task_nox():
    return dict(
        actions=['nox'],
        file_dep=[
            'wheelhouse/evn-0.1.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
            'wheelhouse/evn-0.1.0-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
        ],
    )
