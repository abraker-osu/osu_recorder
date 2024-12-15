import typing
import logging
import time
import os

import watchdog.observers
import watchdog.events

from beatmap_reader import BeatmapIO, BeatmapBase
from replay_reader import ReplayIO, Replay
from osu_db import MapsDB




class EventHandler(watchdog.events.FileSystemEventHandler):

    def __init__(self, callback: typing.Callable[[BeatmapBase | None, Replay], None], maps_db: MapsDB):
        watchdog.events.FileSystemEventHandler.__init__(self)

        self.__logger = logging.getLogger(self.__class__.__name__)

        self.__maps_db  = maps_db
        self.__callback = callback


    def on_created(self, event: watchdog.events.FileSystemEvent):
        if '.osr' not in event.src_path:
            return

        try: self.handle_new_replay(event.src_path)
        except Exception as e:
            self.__logger.error(self.__get_traceback(e, 'Error processing replay'))


    def handle_new_replay(self, replay_file_name: str):
        self.__logger.debug(f'Processing replay: {replay_file_name}')

        # Needed sleep to wait for osu! to finish writing the replay file
        time.sleep(2)

        try: replay = ReplayIO.open_replay(replay_file_name)
        except Exception as e:
            self.__logger.error(self.__get_traceback(e, 'Error opening replay'))
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


    def __get_traceback(self, e: Exception, msg: str):
        traceback_str = ''
        traceback_str += f'{msg}: {type(e).__name__} due to "{e}"\n'

        tb_curr = e.__traceback__
        while tb_curr != None:
            traceback_str += f'    File "{tb_curr.tb_frame.f_code.co_filename}", line {tb_curr.tb_lineno} in {tb_curr.tb_frame.f_code.co_name}\n'
            tb_curr = tb_curr.tb_next

        return traceback_str


class OsuRecorder:

    def __init__(self, osu_path, callback: None | typing.Callable[[BeatmapBase | None, Replay], None] = None):
        self.__observer = watchdog.observers.Observer()

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
        self.__callback = callback
        self.__monitor  = None
        self.__event_handler = EventHandler(self.__callback, self.__maps_db)


    def __del__(self):
        self.stop()


    def stop(self):
        self.__observer.stop()
        self.__monitor = None


    def start(self, callback: None | typing.Callable[[BeatmapBase | None, Replay], None] = None):
        if self.__monitor is not None:
            self.__logger.info(f'Attempted to start replay monitoring when already started')
            return

        if self.__replay_path is None:
            raise TypeError('Replay path is None')

        if callback is not None:
            self.__callback = callback

        if self.__callback is None:
            raise TypeError('callback is None')

        self.__event_handler = EventHandler(self.__callback, self.__maps_db)
        self.__monitor = self.__observer.schedule(self.__event_handler, self.__replay_path, recursive=False)
        self.__logger.info(f'Created replay file creation monitor for {self.__replay_path}')

        self.__observer.start()


    def handle_new_replay(self, replay_file_name: str):
        self.__event_handler.handle_new_replay(replay_file_name)
