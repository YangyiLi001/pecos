#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance
#  with the License. A copy of the License is located at
#
#  http://aws.amazon.com/apache2.0/
#
#  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
#  OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions
#  and limitations under the License.

import codecs
import os
import setuptools
import subprocess
import re
import warnings


class VersionHelper(object):
    """Helper class to figure out current package version from git tag."""
    __VERSION_FP = "pecos/_version.py"
    __VERSION_PY = \
"""
# This file is automatically generated from Git version tag by running setup.
# Only distribution/installed packages contain this file.

__version__ = "%s"
"""

    @classmethod
    def __update_version_py(cls):
        """Update version from git tag infomation.
        If not in git repository or git tag missing, will use a dummy version 0.0.0
        """
        # Dummy version, for non-Git repo installation or tag info missing
        ver = "0.0.0"

        # Check Git repository info for the version
        if os.path.isdir(".git"):
            # Run git describe to get current tag, commit hash is not included
            git_desc = subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                                    stdout=subprocess.PIPE)
            if git_desc.returncode == 0: # Success
                # Clean version tag
                git_tag = git_desc.stdout.decode('utf-8')
                assert re.match(r'v\d+.\d+.\d+', git_tag), f"We use tags like v0.1.0, but got {git_tag}"
                ver = git_tag[len("v"):].strip()

        # If cannot get version info, raise warning
        if ver == "0.0.0":
            warnings.warn(f"Unable to run retrieve version from git info, "
                        f"maybe not in a Git repository, or tag info missing? "
                        f"Will write dummy version 0.0.0 to {cls.__VERSION_FP}")

        # Write version tag
        with open(cls.__VERSION_FP, "w") as ver_fp:
            ver_fp.write(cls.__VERSION_PY % ver)

        assert os.path.isfile(cls.__VERSION_FP), f"{cls.__VERSION_FP} does not exist."
        print(f"Set version to {ver}")

    @classmethod
    def __read_version_file(cls):
        """Read version from file."""
        here = os.path.abspath(os.path.dirname(__file__))
        with codecs.open(os.path.join(here, cls.__VERSION_FP), 'r') as fp:
            return fp.read()

    @classmethod
    def get_version(cls):
        """Get version from git tag and write to file.
        Return version info.
        """
        cls.__update_version_py()
        for line in cls.__read_version_file().splitlines():
            if line.startswith('__version__'):
                delim = '"' if '"' in line else "'"
                return line.split(delim)[1]
        else:
            raise RuntimeError("Unable to find version string.")


class BlasHelper(object):
    """Helper class to figure out user's BLAS library path by Numpy's system-info tool."""

    @classmethod
    def get_blas_lib_dir(cls):
        """Return user's BLAS library found by Numpy's system-info tool. If not found, will raise error."""
        import numpy.distutils.system_info as nps

        blas_info = nps.get_info('lapack_opt')
        assert blas_info, "No BLAS/LAPACK library is found, need to install BLAS."

        blas_lib = blas_info['libraries']
        blas_dir = blas_info['library_dirs']

        assert blas_lib, "No BLAS/LAPACK library is found, need to install BLAS."
        assert blas_dir, "No BLAS/LAPACK library directory is found, need to install BLAS."

        return blas_lib, blas_dir


with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Requirements
numpy_requires = [
    'numpy<1.20.0; python_version<"3.7"', # setup_requires needs correct version for <3.7
    'numpy>=1.19.5; python_version>="3.7"'
]
setup_requires = numpy_requires + [
    'pytest-runner',
    'sphinx_rtd_theme'
]
install_requires = numpy_requires + [
    'scipy>=1.4.1',
    'scikit-learn>=0.24.1',
    'torch>=1.8.0',
    'sentencepiece>=0.1.86,!=0.1.92', # 0.1.92 results in error for transformers
    'transformers>=4.1.1; python_version<"3.9"',
    'transformers>=4.4.2; python_version>="3.9"'
]

# Fetch Numpy before building Numpy-dependent extension, if Numpy required version was not installed
setuptools.dist.Distribution().fetch_build_eggs(numpy_requires)
blas_lib, blas_dir = BlasHelper.get_blas_lib_dir()

# Get extra manual compile args if any
# Example usage:
# > PECOS_MANUAL_COMPILE_ARGS="-Werror" python3 -m pip install  --editable .
manual_compile_args = os.environ.get('PECOS_MANUAL_COMPILE_ARGS', default=None)
if manual_compile_args:
    manual_compile_args = manual_compile_args.split(',')
else:
    manual_compile_args = []

# Compile C/C++ extension
ext_module = setuptools.Extension(
    "pecos.core.libpecos_float32",
    sources=["pecos/core/libpecos.cpp"],
    include_dirs=["pecos/core", "/usr/include/", "/usr/local/include"],
    libraries=["gomp", "gcc"] + blas_lib,
    library_dirs=blas_dir,
    extra_compile_args=["-fopenmp", "-O3", "-std=c++14"] + manual_compile_args,
    extra_link_args=['-Wl,--no-as-needed', f"-Wl,-rpath,{':'.join(blas_dir)}"]
    )

setuptools.setup(
    name="libpecos",
    version=VersionHelper.get_version(),
    description="PECOS - Predictions for Enormous and Correlated Output Spaces",
    url="https://github.com/amzn/pecos",
    author="Amazon.com, Inc.",
    license="Apache 2.0",
    packages=setuptools.find_packages(where="."),
    package_dir={"": "."},
    include_package_data=True,
    ext_modules=[ext_module],
    long_description=long_description,
    long_description_content_type="text/markdown",
    setup_requires=setup_requires,
    install_requires=install_requires,
    tests_require=["pytest"]
)
