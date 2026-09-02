# 샷 스펙 (shot spec) v1

패럴랙스 샷 하나를 정의하는 JSON. 경로는 프로젝트 루트 기준 상대 경로 또는 절대 경로.

```json
{
  "image": "episodes/pilot-test/assets/source.png",
  "depth": "episodes/pilot-test/assets/depth.png",
  "out_dir": "episodes/pilot-test/renders",
  "name": "shot01",
  "resolution": [1920, 1080],
  "fps": 24,
  "duration_s": 10,
  "depth_strength": 0.35,
  "camera": {"move": "push_in", "amplitude": 0.18, "sway": 0.03, "loop": false},
  "fog_density": 0.06
}
```

- `depth_strength`: 평면 변위 크기(평면 폭 대비 비율 느낌으로 0.2~0.5 권장).
- `camera.amplitude`: 카메라가 다가가는 거리(블렌더 단위). 크면 가장자리 왜곡이 드러난다.
- `camera.sway`: 좌우 흔들림 폭. `camera.loop`이 true면 모든 움직임이 사인 곡선으로 시작점에 되돌아온다.
- `fog_density`: 볼륨 안개 밀도. 0이면 안개 없음.
