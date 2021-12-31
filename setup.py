from setuptools import setup, find_packages

with open('VERSION') as verfile:
    version = verfile.read().strip()

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
    name='mdl',
    version=version,
    package_dir={'': '.'},
    packages=find_packages(where='.'),
    python_requires='>=3.6',
    install_requires=['requests[socks]', 'requests', 'clint', 'bdownload'],
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
            'download_3rd_parties = mdl.third_parties:download_3rd_parties',
            'mdl = mdl:main'
        ],
        'distutils.commands': [
            ' clean = CleanCommand'
        ]
    },
    url='https://github.com/Jesseatgao/movie-downloader',
    license='MIT License',
    author='Jesse',
    author_email='changxigao@gmail.com',
    description='A fast movie downloader'
)
