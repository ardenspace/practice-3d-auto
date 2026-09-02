"""루프·깜박임·이징용 순수 수학. bpy를 import하지 않으므로 pytest에서 바로 테스트한다."""

import math


def loop_phase(frame: int, frame_start: int, frame_end: int) -> float:
    """frame_start → 0.0, frame_end+1 → 1.0.

    마지막 프레임 다음이 첫 프레임과 정확히 한 주기 떨어지도록 (길이+1)로 나눈다.
    이렇게 해야 클립을 이어 붙였을 때 위치와 속도가 모두 이어진다.
    """
    return (frame - frame_start) / (frame_end - frame_start + 1)


def loop_offset(t: float, amplitude: float, harmonics: int = 1) -> float:
    """주기 1의 사인 곡선. t=0과 t=1에서 값·기울기가 같다."""
    return amplitude * math.sin(2.0 * math.pi * t * harmonics)


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def flicker_factor(t: float, dips) -> float:
    """가로등 밝기 배율(0~1). dips는 (center, width, depth) 목록, 모두 주기 1 기준.

    가우시안 딥을 주기 경계 양쪽으로 감싸서 계산하므로 순환 클립에서도 매끄럽다.
    """
    factor = 1.0
    for center, width, depth in dips:
        for wrap in (-1.0, 0.0, 1.0):
            d = (t - (center + wrap)) / width
            factor -= depth * math.exp(-d * d)
    return max(0.0, factor)
