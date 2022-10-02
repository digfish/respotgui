"""
   Copyright 2022 digfish

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License."""



import os,sys,io
from re import search
import PySimpleGUI as sg
import websocket
import threading
import requests
import json
from PIL import Image
import time
import pickle
from queue import Queue
import dotenv
from pycaw.pycaw import AudioUtilities
import pynput
import logging
import about


APP_NAME = "ReSpotGUI"
RESPOT_BASE_URL="http://localhost:24879"

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')


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
        global DEBUG
        jst = json.loads(msg)
        #print(json.dumps(jst,indent=4))
        event = jst['event']
        if DEBUG:
            open(f'dumps/{int(time.time()*10)}-{event}.json','w').write(msg)
        if event == 'trackSeeked':
            self.track_timer.reset()
            self.track_timer.set_elapsed(float(jst['trackTime']) / 1000.0)
        elif event == 'playbackPaused': 
            self.window['play_pause'].update('▶')
        elif event == 'playbackResume':
            self.window['play_pause'].update('⏸')
        elif event == 'volumeChanged':
             self.window['slider_volume'].update(int(jst['value'] * 100))
        elif event == 'trackChanged':
            global first_playing
            # if first_playing:
            #     first_playing = False
            # else:
            if not jst['userInitiated']: 
                if len(self.window['-LIST-'].get_indexes()) > 0:
                    change_selected_track(self.window['-LIST-'],+1)
                else:
                    self.window['-LIST-'].update(set_to_index=0)
        elif event == 'metadataAvailable':
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
            self.track_timer.reset()
            self.track_timer.set_total_time(
                float(jst['track']['duration']) / 1000.0)
            
            ## if empty list, fill it
            current_playlist = self.window['-LIST-'].get_list_values()
            if len(current_playlist) == 0 or current_playlist[0] == 'Radio playing. No queue':
                current_playlist = long_operation_result(update_list)
                if len(current_playlist) > 0:
                    self.window['-LIST-'].update(values=current_playlist.values())
                else:
                    self.window['-LIST-'].update(values=['Radio playing. No queue'])
            else: #compare the current playing track with the selected track, if are not equal, refill the playlist
                if songname != current_playlist[0]:
                    current_playlist = long_operation_result(update_list)
                    if len(current_playlist) > 0:
                        self.window['-LIST-'].update(values=current_playlist.values())
                        # clear the selection
                        self.window['-LIST-'].set_value([])

            if not self.timerthread.is_alive():
                self.timerthread.start()


    def get_ws(self):
        return self.ws


class TrackTimer:

    def __init__(self,elapsed=0.0,total_time=0.0):
        self.start_time = time.time()
        self.elapsed = elapsed
        self.total_time = total_time

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

    def get_total_time(self):
        return self.total_time

    def set_total_time(self,total_time):
        self.total_time = total_time

    def format_mmss(self,timesecs):
        return time.strftime("%M:%S", time.gmtime(timesecs))

    def __str__(self):
        elapsed = self.get_elapsed()
#        return time.strftime("%M:%S", time.gmtime(elapsed))
        elapsed_time_str = self.format_mmss(elapsed)
        if self.total_time > 0.0: 
            elapsed_time_str += "/" + self.format_mmss(self.total_time)
        return elapsed_time_str

class TimerThread(threading.Thread):
    def __init__(self,window,track_timer):
        super().__init__()
        self.daemon = True
        self.started = False
        self.window = window
        self.track_timer = track_timer
        self.terminate = False
        self.paused = False
        self.running = False

    def end(self):
        self.terminate = True

    def run(self):
        running = True
        while True:
            if not self.paused:
                try:
                    self.window['currently'].update(self.track_timer)
                    self.window['slider'].update(self.track_timer.get_elapsed())
                    self.window['slider'].set_tooltip(self.track_timer)
                    time.sleep(1)
                except BaseException as ex:
                    logging.warning("Restarting timer thread")
                    #raise ex
                    new_timer_thread = TimerThread(self.window,self.track_timer)
                    new_timer_thread.start()

            if self.terminate:
                break

class MediaKeysListener(pynput.keyboard.Listener):
    def __init__(self,window):
        super().__init__(on_release=self.on_press)
        self.window = window

    def listen(self):
        self.start()
    
    def end(self):
        self.stop()
        self.join()

    def on_press(self,key):
        #print(key)
        if key == pynput.keyboard.Key.media_play_pause:
            self.window['play_pause'].click()
        elif key == pynput.keyboard.Key.media_next:
            self.window['next'].click()
        elif key == pynput.keyboard.Key.media_previous:
            self.window['prev'].click()
            
class SearchLister(dict):

    def __init__(self,type_):
        super().__init__()
        self.typename = type_

    def __str__(self) -> str:
        return f"{self.typename} ({len(self)})"




def set_volume(volume): # 0 - 1
    volume_to_set = float(volume) * 65536.0
    #print(f"Setting volume to {volume_to_set}")
    requests.post(RESPOT_BASE_URL + "/player/set-volume",{'volume': int(volume_to_set)})
    return volume 

def get_java_audio_volume():
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name() == 'java.exe':
            return session.SimpleAudioVolume.GetMasterVolume()
    return 0.5 

def touch_initial_volume():
    requests.post(RESPOT_BASE_URL + '/player/set-volume',{'step': -1 })
            
def album_image(album):
    album_name = album['name']
    album_image = album['coverGroup']['image'][1]
    album_image_token = album_image['fileId']
    album_image_url = 'http://i.scdn.co/image/'+ album_image_token.lower()
    jpgbytes = requests.get(album_image_url).content
    pngbytes = io.BytesIO()
    try:
        Image.open(io.BytesIO(jpgbytes)).save(pngbytes,format='PNG')
        
    except BaseException as e:
        logging.info("Error: " + str(e))
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

def next_tracks():
    global DEBUG
    if DEBUG:
        open('next_tracks.json','wb').write(r.content)
    r = requests.post(RESPOT_BASE_URL + "/player/tracks")
    rjst = r.json()
    tracks = rjst['next']
    uri_trackname_list = map(lambda t: resolve_metadata(t['uri']), tracks)
    formatted_list = dict()
    for urn,trackname in uri_trackname_list:
        formatted_list[urn] = trackname
    try:
        return formatted_list
    except BaseException as e:
        return dict()


def resolve_metadata(uri):
    global cache
    if uri in cache.keys():
        trackname = cache[uri]
    else:
        r = requests.post(RESPOT_BASE_URL + "/metadata/" + uri)
        trackname = r.json()['name']
        cache[uri] = trackname
    return (uri,trackname)

def update_list():
    global DEBUG
    r = requests.get(RESPOT_BASE_URL + "/web-api/v1/me/player/queue")
    if DEBUG:
        open('player_queue.json','wb').write(r.content)
    new_list = dict()
    if 'queue' in r.json().keys() and len(r.json()['queue']) > 0:
        for item in r.json()['queue']:
            new_list[item['uri']] = item['name']
    return new_list

def search_playlist(query):
    global DEBUG
    r = requests.post(RESPOT_BASE_URL + f"/search/:spotify:playlist:{query}")
    if DEBUG:
        open('search_playlist.json','wb').write(r.content)
    rjst = r.json()
    search_lists_grouped = {}
    for search_result_type in rjst['results'].keys():
        search_result_type_lowercase = search_result_type.lower()
        search_lists_grouped[search_result_type_lowercase] = SearchLister(search_result_type_lowercase)
        for hit in rjst['results'][search_result_type]['hits']:
            search_lists_grouped[search_result_type_lowercase][hit['uri']] = hit['name']
    return search_lists_grouped

def highlighted_playlists():
    global DEBUG
    r = requests.get(RESPOT_BASE_URL + "/web-api/v1/browse/featured-playlists")
    if DEBUG:
        open('highlighted_playlists.json','wb').write(r.content)
    rjst = r.json()
    playlist_uri_dict = dict()
    for item in rjst['playlists']['items']:
        playlist_uri_dict[item['uri']] = {'name':item['name'],'id':item['id']}
    return playlist_uri_dict

def user_playlists():
    #r = requests.get(RESPOT_BASE_URL + "/web-api/v1/users/1181906047/playlists")
    r = requests.get(RESPOT_BASE_URL + "/web-api/v1/me/playlists")
    rjst = r.json()
    playlist_uri_dict = dict()
    for item in rjst['items']:
        playlist_uri_dict[item['uri']] = {'name':item['name'],'id':item['id']}
    return playlist_uri_dict

def get_playlist_tracks(playlist_uri):
    global DEBUG
    if type(playlist_uri) == tuple:
        playlist_uri = playlist_uri[0]
    playlist_id = playlist_uri.split(':')[-1]
    r = requests.get(RESPOT_BASE_URL + f"/web-api/v1/playlists/{playlist_id}/tracks")
    if DEBUG:
        open('playlist_tracks.json','wb').write(r.content)
    rjst = r.json()
    tracks = rjst['items']
    track_uri_dict = dict()
    for item in tracks:
        track_uri_dict[item['track']['uri']] = item['track']['name']
    return track_uri_dict

def fetch_categories():
    r = requests.get(RESPOT_BASE_URL + "/web-api/v1/browse/categories")
    rjst = r.json()
    category_id_dict = dict()
    for item in rjst['categories']['items']:
        category_id_dict[item['id']] = item['name']
    return category_id_dict

def category_playlists(category_id):
    r = requests.get(RESPOT_BASE_URL + f"browse/categories/{category_id}/playlists")
    rjst = r.json()
    playlist_uri_dict = dict()
    for item in rjst['playlists']['items']:
        playlist_uri_dict[item['uri']] = {'name':item['name'],'id':item['id']}
    return playlist_uri_dict


def format_time_elapsed(elapsed):
    return time.strftime("%M:%S", time.gmtime(elapsed))

def change_selected_track(tracks_list_elem,step):
    curr_sel = tracks_list_elem.get_indexes()
    if len(curr_sel) > 0:
        selected_index = tracks_list_elem.get_indexes()[0]
        tracks_list_elem.update(set_to_index=selected_index + step)
    else:
        tracks_list_elem.update(set_to_index=0)

def long_operation_result(function,*args):
    """_summary_ : Runs a function in a separate thread and returns a result when it's done.

    Args:
        function (_callable_): _any function with any number of parameters_
        *args (_any_): _any number of parameters to be passed to the called function_

    Returns:
        _any_: _the return value of the function passed in_
    """
    queue = Queue()
    operation_thread = threading.Thread(target=lambda queue: queue.put(function(*args)),args=(queue,))
    operation_thread.start()
    operation_thread.join()
    return queue.get()


def main():
    """Main function"""
    global cache,first_playing
    playing = False
    first_playing = True
    repeat_mode = "none"

    global DEBUG
    DEBUG = dotenv.load_dotenv() != False

    active_playlist = dict()
    file_curdir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(file_curdir + '/cache.pickle'):
        cache = pickle.load(open(file_curdir+"/cache.pickle", "rb"))
    else:
        cache = {}

    try:
        resp = requests.post(RESPOT_BASE_URL + '/player/current' )
    except (ConnectionRefusedError,requests.exceptions.ConnectionError):
        sg.popup_error("ReSpot is not running\nLaunch it with java -jar librespot-api-1.6.2.jar")
        logging.error("ReSpot is not running")
        exit(-1)
    try:
        playing_label = currently_playing(resp.json())
        album_icon_bytes = album_image(resp.json()['track']['album'])
        already_elapsed = float(resp.json()['trackTime']) / 1000.0
        total_track_time = float(resp.json()['track']['duration']) / 1000.0
        playing = True
    except KeyError as ke:
        logging.warning(ke,ke.with_traceback)
        playing_label = "Nothing is playing. Search for something to play."
        logging.info("Nothing is playing")
        imagefilepath = file_curdir + '/img/no-music.png'
        with open(imagefilepath,'rb') as fp_image:
            pngbytes = io.BytesIO()
            Image.open(fp_image).save(pngbytes,format='PNG')
            album_icon_bytes = pngbytes.getvalue()            
        already_elapsed = 0.0
        total_track_time = 0.0
       
    controls_layout = [
        [sg.Text(format_time_elapsed(already_elapsed),key='currently'), 
         sg.Slider(range=(0, total_track_time),disable_number_display=True, orientation='h', size=(15, 15), default_value=already_elapsed, 
            key='slider', enable_events=True)],
        [sg.Text(playing_label,size=(40, 1), key='-OUTPUT-')] ,
        [sg.Button('⏪', key='prev'),
         sg.Button('⏸' if playing else '▶',key='play_pause'),
         sg.Button('⏩', key='next'),
         sg.Button('🔀',key='shuffle',button_color=('green'),tooltip='Shuffle'),
         sg.Button("🔁",key='repeat',button_color=('green'),tooltip=f"Repeat: {repeat_mode}"),
         sg.Slider(range=(0,100),default_value=50,orientation='h',size=(15,15),enable_events=True,
            key='slider_volume')
        ],
    ]
    results_search_root = sg.TreeData()
    results_search_elem = sg.Tree(data=results_search_root,headings=[],show_expanded=False,key='search_results',
        expand_x=True,expand_y=True,enable_events=True);
    # Define the window's contents
    layout = [  
                [
                sg.Column( [
                    [sg.Image(album_icon_bytes,key='-ICON-'),sg.Column(controls_layout)],
                    [sg.Input(default_text='Search',key='input_search',size=(20,),enable_events=True),
                        sg.Submit('search',key='search_button') ],
                    [results_search_elem]
                ],vertical_alignment='top',expand_y=True),
                sg.Listbox([],auto_size_text=True,size=(40,20),key='-LIST-',enable_events=True,bind_return_key=True)
                ] 
    ]


    # Create the window
    window = sg.Window(f"{APP_NAME} => {playing_label}" , layout, font=('Verdana',10), finalize=True)
    # remove the tree header row
    results_search_elem.Widget['show'] = 'tree'
    track_timer = TrackTimer(already_elapsed,total_track_time)
    timerthread = TimerThread(window,track_timer)
    wsthread = WsThread(window,track_timer,timerthread)

    active_playlist = long_operation_result(update_list)

    window['-LIST-'].update(active_playlist.values())

    results_search_root.insert('','featured_playlists','Featured Playlists',[])
    featured_playlists = long_operation_result(highlighted_playlists)
    for urn_key in featured_playlists:
        result = featured_playlists[urn_key] 
        results_search_root.insert('featured_playlists',urn_key,result['name'],[result])

    results_search_root.insert('','user_playlists','User Playlists',[])
    user_playlists_ = long_operation_result(user_playlists)
    for urn_key in user_playlists_:
        result = user_playlists_[urn_key] 
        results_search_root.insert('user_playlists',urn_key,result['name'],[result])
    
    
    window['search_results'].update(results_search_root)

    
    if playing and not timerthread.is_alive():
        timerthread.start()
 
    wsthread.start()

    keys_listener = MediaKeysListener(window)
    keys_listener.start()

    #set initial volume
    threading.Thread(target=touch_initial_volume).start()

    # set about menu
    #show_about(window)

    shuffle_enabled = False
    while True:                               
    # Display and interact with the Window
        event, values = window.read()
        if event == 'prev':
            r = requests.post(RESPOT_BASE_URL + '/player/prev')
            change_selected_track(window['-LIST-'],-1)
        elif event == 'next':
            r = requests.post(RESPOT_BASE_URL + '/player/next')
            change_selected_track(window['-LIST-'],+1)
        elif event == 'play_pause':
            current_button = window['play_pause'].get_text()
            if current_button == '⏸': #pause
                requests.post(RESPOT_BASE_URL + '/player/pause')
                already_elapsed = track_timer.get_elapsed()
                timerthread.paused = True
                playing = False
            else: #resume
                requests.post(RESPOT_BASE_URL + '/player/resume')
                track_timer.resume(already_elapsed)
                timerthread.paused = False
                playing = True
            new_button_icon = '⏸' if current_button == '▶' else '▶'
            window['play_pause'].update(new_button_icon)
        elif event == 'shuffle':
            shuffle_enabled = not shuffle_enabled
            requests.post(RESPOT_BASE_URL + '/player/shuffle',{'val':'enabled' if shuffle_enabled else 'disabled'})
            window['shuffle'].set_tooltip(shuffle_enabled)
            window['shuffle'].update(button_color=('green' if not shuffle_enabled else 'red'))
            active_playlist = long_operation_result(update_list)
            window['-LIST-'].update(active_playlist.values())
            window['-LIST-'].update(set_to_index=0)    
        elif event == 'repeat':
            if repeat_mode == 'none':
                repeat_mode = 'track'
                button_color = 'red'
            elif repeat_mode == 'track':
                repeat_mode = 'context'
                button_color = 'pink' 
            else:   
                repeat_mode = 'none'
                button_color = 'green'
            requests.post(RESPOT_BASE_URL + f'/player/repeat',{'val':repeat_mode})
            window['repeat'].set_tooltip(f'Repeat mode: {repeat_mode}')
            window['repeat'].update(button_color=button_color)      
        elif event == '-LIST-': #click in the playlist listbox
            selected_index = window['-LIST-'].get_indexes()[0]
            urn = list(active_playlist.keys())[selected_index]
            requests.post(RESPOT_BASE_URL + '/player/load',{'uri':urn})
            requests.post(RESPOT_BASE_URL + '/player/play-pause')
        elif event == 'search_button': # click in the "search playlists" button
            results_search_root = sg.TreeData() #empties the search results tree
            search_results = search_playlist(values['input_search'])
            front_playlists = search_results
            for category  in search_results:
                results_in_category = search_results[category] 
                results_search_root.insert('',category,results_in_category,[])
                for urn_key in results_in_category:
                    itemname = results_in_category[urn_key] 
                    results_search_root.insert(category,urn_key,itemname,[urn_key,itemname])
            window['search_results'].update(results_search_root)
            window['search_results'].expand(expand_row=False)

        elif event == 'search_results': # click in the listbox of search results
            node_key = values[event][0]
            logging.debug(f"node_key: {node_key}")
            node_content = window['search_results'].TreeData.tree_dict[node_key]
            logging.debug(f"node_content: {node_content}")
            category = node_content.parent
            if len(category.strip()) == 0: # root node, does nothing
                continue
            requests.post(RESPOT_BASE_URL + '/player/load',{'uri':node_key})
            requests.post(RESPOT_BASE_URL + '/player/play-pause')

            if category in ['playlists']:
                urn = node_key
                active_playlist = long_operation_result(get_playlist_tracks,urn)
            else:
                active_playlist = long_operation_result(update_list)

            if len(active_playlist) > 0:
                window['-LIST-'].update(active_playlist.values())
                window['-LIST-'].update(set_to_index=0)
            else:
                window['-LIST-'].update(['No tracks'])
            first_playing = True
            if not playing:
                playing = True
                window['play_pause'].update('⏸')
                if not timerthread.running:
                    timerthread.start()
            
        elif event == 'input_search':
            if values['input_search'] == 'Search':
                window['input_search'].update('')
        elif event == 'slider':
            requests.post(RESPOT_BASE_URL + f"/player/seek",{'pos':int(values['slider']) * 1000})
            logging.debug("seeking to " + str(values['slider']))
            track_timer.set_elapsed(values['slider'])
        elif event == 'slider_volume':
            #print(f"Volume set to {values['slider_volume']}")
            set_volume(values['slider_volume']/100.0)
        elif event == '-TIMEOUT-':
            logging.debug(event,values)
        elif event == sg.WIN_CLOSED or event == 'dismiss': # if user closes window or clicks cancel
            timerthread.end()
            break
        else:
            logging.debug(event,'=>',values)

    pickle.dump(cache,open(file_curdir + '/cache.pickle','wb'))
    window.close()
    wsthread.get_ws().close()
    timerthread.join()
    wsthread.join()
    keys_listener.end()                              
    

if __name__ == "__main__":
    main()
