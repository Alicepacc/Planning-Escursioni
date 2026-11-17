from cordata_ingest.build.graph import DIFFICULTY, difficulty_of, tile_of, up_down


def test_tile_of_divides_the_area_in_fixed_cells():
    assert tile_of(11.5218, 46.149) == (115, 922)
    assert tile_of(11.5999, 46.1499) == (115, 922)
    assert tile_of(11.6001, 46.1501) == (116, 923)
    # sul bordo esatto decide la virgola mobile, identica in Python e in JavaScript (graph.ts)
    assert tile_of(11.6, 46.15) == (115, 922)


def test_difficulty_prefers_the_official_cai_scale():
    # il catasto vince su sac_scale; con più sentieri conta il grado più alto
    assert difficulty_of("path", "mountain_hiking", ["EE"]) == DIFFICULTY["EE"]
    assert difficulty_of("path", "alpine_hiking", ["E", "T"]) == DIFFICULTY["E"]
    assert difficulty_of("path", None, ["EEA:F"]) == DIFFICULTY["EEA"]


def test_difficulty_falls_back_to_osm():
    assert difficulty_of("via_ferrata", None, None) == DIFFICULTY["EEA"]
    assert difficulty_of("path", "demanding_mountain_hiking", None) == DIFFICULTY["EE"]
    assert difficulty_of("path", None, None) == DIFFICULTY["E"]
    assert difficulty_of("track", None, []) == DIFFICULTY["T"]


def test_up_down_ignores_dem_noise():
    assert up_down([1000, 1001, 1000, 1002, 1001]) == (0, 0)
    assert up_down([1000, 1010, 1005, 1020]) == (25, 5)
