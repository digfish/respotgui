import os,sys,io
import PySimpleGUI as sg
import websocket
import threading
import requests
import json
from PIL import Image

APP_NAME = "ReSpotGUI"
RESPOT_BASE_URL="http://localhost:24879"
global window

class WsThread(threading.Thread):
    def __init__(self,window):
        super().__init__()
        self.daemon = True
        self.ws = websocket.WebSocketApp("ws://localhost:24879/events",
                                on_message=self.on_message)

        self.window = window

    def run(self):
        self.ws.run_forever()

    def on_message(self,ws,msg):
        jst = json.loads(msg)
        #print(json.dumps(jst,indent=4))
        event = jst['event']
        if event == 'metadataAvailable':
            track = jst['track']
            songname = track['name']
            artist = track['artist'][0]
            artistname = artist['name']
            title = f"{artistname} - {songname}"
            self.window['-OUTPUT-'].update(title)
            self.window.set_title(f"{APP_NAME} => {title}")
            album = track['album']
            album_name = album['name']
            album_image = album['coverGroup']['image'][1]
            album_image_token = album_image['fileId']
            album_image_url = 'http://i.scdn.co/image/'+ album_image_token.lower()
            #print("Album image url: " + album_image_url)
            jpgbytes = requests.get(album_image_url).content
            pngbytes = io.BytesIO()
            try:
                Image.open(io.BytesIO(jpgbytes)).save(pngbytes,format='PNG')
                #open(album_name+'.png','wb').write(pngbytes.getvalue())
                self.window['-ICON-'].update(data=pngbytes.getvalue())
            except BaseException as e:
                print("Error: " + str(e))
                pass
            #self.window.refresh()


    def get_ws(self):
        return self.ws



def main():

    column_layout = [
        [sg.Text("Currently Playing")],
        [sg.Text(size=(40, 1), key='-OUTPUT-')] ,
        [ sg.Button('<'),sg.Button('||'),sg.Button('>'), sg.Button('dismiss')]
    ]
    # Define the window's contents
    layout = [  
                [sg.Image('respot/no-music.png',key='-ICON-'),sg.Column(column_layout)] 
    ]

    # Create the window
    window = sg.Window(APP_NAME, layout)

    thread = WsThread(window)

    thread.start()

    while True:                               
    # Display and interact with the Window
        event, values = window.read() 
        if event == '<':
            r = requests.post(RESPOT_BASE_URL + '/player/prev')
        elif event == '>':
            r = requests.post(RESPOT_BASE_URL + '/player/next')
        elif event == '||':
            r = requests.post(RESPOT_BASE_URL + '/player/play-pause')

        elif event == sg.WIN_CLOSED or event == 'dismiss': # if user closes window or clicks cancel
            break
    window.close()
    thread.get_ws().close()
    thread.join()                               
    

if __name__ == "__main__":
    main()
