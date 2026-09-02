import math

from pipeline.scenes.motion import flicker_factor, loop_offset, loop_phase, smoothstep


def test_loop_phase_starts_at_zero_and_wraps_before_one():
    assert loop_phase(1, 1, 48) == 0.0
    assert loop_phase(48, 1, 48) < 1.0
    # frame_end+1 은 정확히 한 바퀴(1.0)라서 다음 클립의 첫 프레임과 이어진다
    assert math.isclose(loop_phase(49, 1, 48), 1.0)


def test_loop_offset_is_periodic():
    assert math.isclose(loop_offset(0.0, 0.5), loop_offset(1.0, 0.5), abs_tol=1e-9)
    assert math.isclose(loop_offset(0.25, 0.5), 0.5)
    assert math.isclose(loop_offset(0.25, 0.5, harmonics=2), 0.0, abs_tol=1e-9)


def test_smoothstep_clamps_and_eases():
    assert smoothstep(-1.0) == 0.0
    assert smoothstep(2.0) == 1.0
    assert math.isclose(smoothstep(0.5), 0.5)
    assert smoothstep(0.1) < 0.1  # 시작이 느리다


def test_flicker_factor_dips_only_near_centers():
    dips = [(0.5, 0.01, 0.6)]
    assert math.isclose(flicker_factor(0.5, dips), 0.4, abs_tol=1e-6)
    assert flicker_factor(0.1, dips) > 0.99
    # 주기 경계를 넘어가는 딥도 양쪽에서 같은 값이 나온다(순환)
    wrap = [(0.0, 0.02, 0.5)]
    assert math.isclose(flicker_factor(0.995, wrap), flicker_factor(0.005, wrap), abs_tol=1e-9)
