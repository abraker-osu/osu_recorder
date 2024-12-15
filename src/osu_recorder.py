import typing
import logging
import time
import os

import watchdog.observers
import watchdog.events

from beatmap_reader import BeatmapIO, BeatmapBase
from replay_reader import ReplayIO, Replay
from osu_db import MapsDB



def get_traceback(e: Exception, msg: str):
    traceback_str = ''
    traceback_str += f'{msg}: {type(e).__name__} due to "{e}"\n'

    tb_curr = e.__traceback__
    while tb_curr != None:
        traceback_str += f'    File "{tb_curr.tb_frame.f_code.co_filename}", line {tb_curr.tb_lineno} in {tb_curr.tb_frame.f_code.co_name}\n'
        tb_curr = tb_curr.tb_next

    return traceback_str



class OsuRecorder(watchdog.observers.Observer):

    def __init__(self, osu_path):
        watchdog.observers.Observer.__init__(self)

        self.__stream_handler = logging.StreamHandler()
        self.__stream_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s  [ %(name)s ] %(message)s'))

        self.__logger = logging.getLogger(self.__class__.__name__)
        self.__logger.addHandler(self.__stream_handler)

        if not os.path.isdir(osu_path):
            raise FileNotFoundError(f'Invalid osu! path: "{osu_path}"')

        self.__replay_path = f'{osu_path}/Data/r'
        if not os.path.exists(self.__replay_path):
            self.__replay_path = None
            raise FileNotFoundError(f'"{self.__replay_path}" does not exist!')

        self.__maps_db  = MapsDB(osu_path)
        self.__callback = None
        self.__monitor  = None


    def __del__(self):
        self.stop()


    def stop(self):
        watchdog.observers.Observer.stop(self)
        self.__monitor = None


    def start(self, callback: typing.Callable[[BeatmapBase, Replay], None]):
        if self.__monitor is not None:
            self.__logger.info(f'Attempted to start replay monitoring when already started')
            return

        if self.__replay_path is None:
            raise TypeError('Replay path is None')

        self.__callback = callback

        class EventHandler(watchdog.events.FileSystemEventHandler):
            __logger = self._OsuRecorder__logger
            __reply_handler = self._OsuRecorder__handle_new_replay

            def on_created(self, event):
                if '.osr' not in event.src_path:
                    return

                try: EventHandler.__reply_handler(event.src_path)
                except Exception as e:
                    EventHandler.__logger.error(get_traceback(e, 'Error processing replay'))

        self.__monitor = self.schedule(EventHandler(), self.__replay_path, recursive=False)
        self.__logger.info(f'Created replay file creation monitor for {self.__replay_path}')

        watchdog.observers.Observer.start(self)


    def __handle_new_replay(self, replay_file_name: str):
        self.__logger.debug(f'Processing replay: {replay_file_name}')

        # Needed sleep to wait for osu! to finish writing the replay file
        time.sleep(2)

        try: replay = ReplayIO.open_replay(replay_file_name)
        except Exception as e:
            self.__logger.error(get_traceback(e, 'Error opening replay'))
            return

        self.__logger.debug('Determining beatmap...')

        map_file_name = self.__maps_db.get_map_file_name(replay.beatmap_hash)
        if map_file_name is None:
            self.__logger.info(f'file_name is None. Unable to open map for replay with beatmap hash {replay.beatmap_hash}')

            self.__callback(None,  replay)
            return

        try: beatmap = BeatmapIO.open_beatmap(map_file_name)
        except FileNotFoundError:
            self.__logger.warning(f'Map {map_file_name} does not exist!')
            return

        self.__callback(beatmap, replay)
