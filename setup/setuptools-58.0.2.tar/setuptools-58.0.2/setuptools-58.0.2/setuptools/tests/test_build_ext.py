import os
import sys
import distutils.command.build_ext as orig
from distutils.sysconfig import get_config_var

from jaraco import path

from setuptools.command.build_ext import build_ext, get_abi3_suffix
from setuptools.dist import Distribution
from setuptools.extension import Extension

from . import environment
from .textwrap import DALS


IS_PYPY = '__pypy__' in sys.builtin_module_names


class TestBuildExt:
    def test_get_ext_filename(self):
        """
        Setuptools needs to give back the same
        result as distutils, even if the fullname
        is not in ext_map.
        """
        dist = Distribution()
        cmd = build_ext(dist)
        cmd.ext_map['foo/bar'] = ''
        res = cmd.get_ext_filename('foo')
        wanted = orig.build_ext.get_ext_filename(cmd, 'foo')
        assert res == wanted

    def test_abi3_filename(self):
        """
        Filename needs to be loadable by several versions
        of Python 3 if 'is_abi3' is truthy on Extension()
        """
        print(get_abi3_suffix())

        extension = Extension('spam.eggs', ['eggs.c'], py_limited_api=True)
        dist = Distribution(dict(ext_modules=[extension]))
        cmd = build_ext(dist)
        cmd.finalize_options()
        assert 'spam.eggs' in cmd.ext_map
        res = cmd.get_ext_filename('spam.eggs')

        if not get_abi3_suffix():
            assert res.endswith(get_config_var('EXT_SUFFIX'))
        elif sys.platform == 'win32':
            assert res.endswith('eggs.pyd')
        else:
            assert 'abi3' in res

    def test_ext_suffix_override(self):
        """
        SETUPTOOLS_EXT_SUFFIX variable always overrides
        default extension options.
        """
        dist = Distribution()
        cmd = build_ext(dist)
        cmd.ext_map['for_abi3'] = ext = Extension(
            'for_abi3',
            ['s.c'],
            # Override shouldn't affect abi3 modules
            py_limited_api=True,
        )
        # Mock value needed to pass tests
        ext._links_to_dynamic = False

        if not IS_PYPY:
            expect = cmd.get_ext_filename('for_abi3')
        else:
            # PyPy builds do not use ABI3 tag, so they will
            # also get the overridden suffix.
            expect = 'for_abi3.test-suffix'

        try:
            os.environ['SETUPTOOLS_EXT_SUFFIX'] = '.test-suffix'
            res = cmd.get_ext_filename('normal')
            assert 'normal.test-suffix' == res
            res = cmd.get_ext_filename('for_abi3')
            assert expect == res
        finally:
            del os.environ['SETUPTOOLS_EXT_SUFFIX']


def test_build_ext_config_handling(tmpdir_cwd):
    files = {
        'setup.py': DALS(
            """
            from setuptools import Extension, setup
            setup(
                name='foo',
                version='0.0.0',
                ext_modules=[Extension('foo', ['foo.c'])],
            )
            """),
        'foo.c': DALS(
            """
            #include "Python.h"

            #if PY_MAJOR_VERSION >= 3

            static struct PyModuleDef moduledef = {
                    PyModuleDef_HEAD_INIT,
                    "foo",
                    NULL,
                    0,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL
            };

            #define INITERROR return NULL

            PyMODINIT_FUNC PyInit_foo(void)

            #else

            #define INITERROR return

            void initfoo(void)

            #endif
            {
            #if PY_MAJOR_VERSION >= 3
                PyObject *module = PyModule_Create(&moduledef);
            #else
                PyObject *module = Py_InitModule("extension", NULL);
            #endif
                if (module == NULL)
                    INITERROR;
            #if PY_MAJOR_VERSION >= 3
                return module;
            #endif
            }
            """),
        'setup.cfg': DALS(
            """
            [build]
            build_base = foo_build
            """),
    }
    path.build(files)
    code, output = environment.run_setup_py(
        cmd=['build'], data_stream=(0, 2),
    )
    assert code == 0, '\nSTDOUT:\n%s\nSTDERR:\n%s' % output
