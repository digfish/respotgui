import subprocess
import os,sys
import setuptools
import versioneer
import configparser


def increment_version(current_version):
    version = current_version.split('.')
    version[-1] = str(int(version[-1]) + 1)
    return '.'.join(version)

def get_version():
    try:
        with open('VERSION', 'r') as f:
            version = f.read().strip()
    except FileNotFoundError:
        version = '0.0.0'
    return version

def store_version(last_version):
    with open('VERSION', 'w') as f:
        f.write(last_version)

if __name__ == '__main__':

    cfg = configparser.ConfigParser()
    cfg.read('setup.cfg')
    current_directory = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(current_directory, 'README.md'), encoding='utf-8') as f:
            long_description = f.read()
    except Exception:
        long_description = ''
    """ 
    cur_version = get_version()
    new_version = increment_version(cur_version)
    store_version(new_version)
    """
    setuptools.setup(
        name='respotgui',
        version=cfg['bumpversion']['current_version'],
#        version=open('VERSION','r').read().strip(),
#        version=versioneer.get_version(),
#        cmdclass=versioneer.get_cmdclass(),
        author="digfish",
        author_email="digfish@digfish.org",
        description=(
            "A frontend for the respot-java Spotify client"
        ),
        long_description=long_description,
        long_description_content_type='text/markdown',
        license="Apache License 2.0",
        url="https://github.com/digfish/respogui",
        packages=setuptools.find_packages(),
        classifiers=[
            "Development Status :: 2 - Pre-Alpha",
            "Environment :: Win32 (MS Windows)",
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: Microsoft :: Windows",
        ],
        entry_points={
            'console_scripts': [
                'respotgui=respot.gui:main'
            ],
#             'gui_scripts': [
#                'respotgui=respot:main'
#            ]
        },
        include_package_data=True,
        package_data={'respot':['img/no-music.png']},
#        install_requires=['PySimpleGUI', 'websocket-client', 'requests', 'Pillow','python-dotenv','pycaw']
        install_requires=open("requirements.txt").read().splitlines()
    )
