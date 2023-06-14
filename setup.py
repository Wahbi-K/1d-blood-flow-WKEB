import os

from setuptools import setup, find_packages


def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


extra_files = package_files('DataFiles')

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

_submodules = ['desist @ file://localhost/%s/in-silico-trial/' % os.getcwd().replace('\\', '/')]

setup(
    name="bloodflow",
    version="0.0.1",
    description='One-dimensional blood flow model',
    author='Raymond Padmos',
    author_email='r.m.padmos@uva.nl',
    packages=find_packages(include=['Blood_Flow_1D']),
    package_data={'': extra_files},
    include_package_data=True,
    install_requires=_submodules+required,
)
