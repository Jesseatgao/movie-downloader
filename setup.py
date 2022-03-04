from setuptools import setup, find_packages
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, 'VERSION'), 'r', 'utf-8') as fd:
    version = fd.read().strip()

with codecs.open(os.path.join(here, 'README.md'), 'r', 'utf-8') as fd:
    long_description = fd.read()

# empty the log file first before packaging
with open('mdl/log/mdl.log', mode='w') as logfile:
    pass

# Extends the Setuptools `clean` command
with open('mdl/third_parties/setupext_janitor/janitor.py') as setupext_janitor:
    exec(setupext_janitor.read())

# try:
#     from setupext_janitor import janitor
#     CleanCommand = janitor.CleanCommand
# except ImportError:
#     CleanCommand = None

cmd_classes = {}
if CleanCommand is not None:
    cmd_classes['clean'] = CleanCommand

setup(
    name='movie-downloader',
    version=version,
    package_dir={'': '.'},
    packages=find_packages(where='.'),
    python_requires='>=3.6',
    install_requires=['bdownload'],
    include_package_data=True,
    package_data={
        'mdl': [
            'log/mdl.log',
            'conf/*.conf',
            'third_parties/aria2/README',
            'third_parties/ffmpeg/README',
            'third_parties/mkvtoolnix/README',
            'third_parties/setupext_janitor/janitor.py', 'third_parties/setupext_janitor/README.rst'
        ]
    },
    setup_requires=[],
    cmdclass=cmd_classes,
    entry_points={
        'console_scripts': [
            'mdl_3rd_parties = mdl.third_parties:download_3rd_parties',
            'mdl = mdl:main'
        ],
        'distutils.commands': [
            ' clean = CleanCommand'
        ]
    },
    url='https://github.com/Jesseatgao/movie-downloader',
    license='MIT License',
    author='Jesse Gao',
    author_email='changxigao@gmail.com',
    description='A fast movie downloader using Aria2',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ]
)
