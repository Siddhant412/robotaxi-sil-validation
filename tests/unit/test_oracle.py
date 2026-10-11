from validation.oracles import stopped_at


def test_observation_oracle_rejects_nearby_moving_vehicle():
    assert not stopped_at(
        [
            {
                "observation": {
                    "edge": "e1",
                    "lane_pos": 100,
                    "stopped": False,
                    "speed": 2,
                }
            }
        ],
        "e1",
        100,
    )
    assert not stopped_at(
        [{"observation": {"edge": "e2", "lane_pos": 100, "stopped": True, "speed": 0}}],
        "e1",
        100,
    )
