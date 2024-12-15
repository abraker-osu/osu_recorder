import logging

from beatmap_reader import BeatMap
from replay_reader import Replay
from osu_analysis import StdMapData, StdReplayData, StdScoreData
from osu_recorder import OsuRecorder



def ar_to_ms(ar: float) -> float:
    if ar <= 5: return 1800 - 120*ar
    else:       return 1950 - 150*ar


def ms_to_ar(ms: float) -> float:
    if ms >= 1200: return (1800 - ms)/120
    else:          return (1950 - ms)/150


def cs_to_px(cs: float) -> float:
    # From https://github.com/ppy/osu/blob/master/osu.Game.Rulesets.Osu/Objects/OsuHitObject.cs#L137
    return (108.8 - 8.96*cs)


def play_handler(beatmap: BeatMap, replay: Replay):
    print(beatmap, replay)

    replay_data = StdReplayData.get_replay_data(replay)

    if beatmap is None:
        return

    map_data = StdMapData.get_map_data(beatmap)

    settings = StdScoreData.Settings()
    settings.ar_ms = ar_to_ms(beatmap.difficulty.ar)
    settings.hitobject_radius = cs_to_px(beatmap.difficulty.cs)/2
    settings.pos_hit_range      = 100   # ms point of late hit window
    settings.neg_hit_range      = 100   # ms point of early hit window
    settings.pos_hit_miss_range = 100   # ms point of late miss window
    settings.neg_hit_miss_range = 100   # ms point of early miss window

    score_data = StdScoreData.get_score_data(replay_data, map_data, settings)
    print(score_data)



if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)

    osu_path = 'K:/Games/osu!'
    recorder = OsuRecorder(osu_path)
    recorder.start(play_handler)

    print('running...')

    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass
