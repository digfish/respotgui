
import os,sys
import PySimpleGUI as sg

ABOUT_TEXT='''
Respot %s by digfish(pescadordigital@gmail.com)
https://pypi.org/project/respotgui
Python version %s
'''

def about():
    current_directory = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_directory,'VERSION.txt'),'r') as f:
        version = f.read()
    python_version = sys.version.split('|')[0]
    sg.Window('About', [[sg.Text(ABOUT_TEXT % (version,python_version))], [sg.Button('OK')]]).read(close=True)

def main():
    about()

if __name__ == "__main__":
    main()
