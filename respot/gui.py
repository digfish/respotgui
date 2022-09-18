import os,sys,io
import PySimpleGUI as sg
import websocket
import threading
import requests
import json
from PIL import Image
import time

APP_NAME = "ReSpotGUI"
RESPOT_BASE_URL="http://localhost:24879"

    

class WsThread(threading.Thread):
    def __init__(self,window,track_timer,timerthread):
        super().__init__()
        self.daemon = True
        self.ws = websocket.WebSocketApp("ws://localhost:24879/events",
                                on_message=self.on_message)
        self.window = window
        self.track_timer = track_timer
        self.timerthread = timerthread


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

            album_icon_bytes = album_image(album)
            self.window['-ICON-'].update(data=album_icon_bytes)
            if not self.timerthread.started:
                self.timerthread.started = True
                self.timerthread.start()
            self.track_timer.reset()

    def get_ws(self):
        return self.ws


class TrackTimer:

    def __init__(self,elapsed=0.0):
        self.start_time = time.time()
        self.elapsed = elapsed

    def get_elapsed(self):
        return time.time() - self.start_time + self.elapsed

    def set_elapsed(self,elapsed):
        self.elapsed = elapsed

    def reset(self):
        self.start_time = time.time()
        self.set_elapsed(0)

    def resume(self,elapsed=0):
        self.reset()
        self.set_elapsed(elapsed)

    def __str__(self):
        elapsed = self.get_elapsed()
        return time.strftime("%M:%S", time.gmtime(elapsed))



class TimerThread(threading.Thread):
    def __init__(self,window,track_timer):
        super().__init__()
        self.daemon = True
        self.started = False
        self.window = window
        self.track_timer = track_timer
        self.terminate = False
        self.paused = False

    def run(self):
        while True:
            if not self.paused:
                self.window['currently'].update(self.track_timer)
                time.sleep(1)
            if self.terminate:
                break


def album_image(album):
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
    except BaseException as e:
        print("Error: " + str(e))
        pass
    return pngbytes.getvalue()



def currently_playing(jtree):
    track = jtree['track']
    songname = track['name']
    artist = track['artist'][0]['name']
    album = track['album']['name']
    mins = int(float(jtree['trackTime']) / (1000 * 60))
    secs = int((float(jtree['trackTime']) / (1000)) % 60)
    time = f"{mins}m {secs}s"
    return f"{artist} - {songname}"


def main():
    file_curdir = os.path.dirname(os.path.abspath(__file__))
    try:
        resp = requests.post(RESPOT_BASE_URL + '/player/current' )
    except (ConnectionRefusedError,requests.exceptions.ConnectionError):
        sg.popup_error("ReSpot is not running\nLaunch it with java -jar librespot-api-1.6.2.jar")
        print("ReSpot is not running")
        sys.exit(1)
    try:
        playing_label = currently_playing(resp.json())
        album_icon_bytes = album_image(resp.json()['track']['album'])
        already_elapsed = float(resp.json()['trackTime']) / 1000.0
        playing = True
    except KeyError:
        playing_label = "Nothing is playing"
        album_icon_bytes = bytes()
        already_elapsed = 0.0
        playing = False


    column_layout = [
        [sg.Text(time.strftime("%M:%S", time.gmtime(already_elapsed)),key='currently')],
        [sg.Text(playing_label,size=(40, 1), key='-OUTPUT-')] ,
        [ sg.Button('<<',key='prev'),sg.Button('||',key='play_pause'),sg.Button('>>',key='next'), sg.Button('dismiss')]
    ]
    # Define the window's contents
    layout = [  
                [sg.Image(album_icon_bytes,key='-ICON-'),sg.Column(column_layout)] 
    ]

    # Create the window
    window = sg.Window(f"{APP_NAME} => {playing_label}" , layout)
    window.finalize()
    track_timer=TrackTimer(already_elapsed)

    timerthread_locker = threading.RLock()

    timerthread = TimerThread(window,track_timer)


    wsthread = WsThread(window,track_timer,timerthread)
 
    if playing:
        timerthread.started = True
        timerthread.start()
 
    wsthread.start()

    while True:                               
    # Display and interact with the Window
        event, values = window.read() 
        if event == 'prev':
            r = requests.post(RESPOT_BASE_URL + '/player/prev')
        elif event == 'next':
            r = requests.post(RESPOT_BASE_URL + '/player/next')
        elif event == 'play_pause':
            r = requests.post(RESPOT_BASE_URL + '/player/play-pause')
            current_button = window['play_pause'].get_text()
            if current_button == '||': #pause
                already_elapsed = track_timer.get_elapsed()
                timerthread.paused = True
            else: #resume
                track_timer.resume(already_elapsed)
                timerthread.paused = False
            new_button_icon = '||' if current_button == '▶' else '▶'
            window['play_pause'].update(new_button_icon)
            

        elif event == sg.WIN_CLOSED or event == 'dismiss': # if user closes window or clicks cancel
            timerthread.terminate = True
            break
    window.close()
    wsthread.get_ws().close()
    timerthread.join()
    wsthread.join()                               
    

if __name__ == "__main__":
    main()
