# 샷 스펙 (shot spec) v2

패럴랙스 샷 하나를 정의하는 JSON. 경로는 프로젝트 루트 기준 상대 경로 또는 절대 경로.

```json
{
  "image": "episodes/pilot-test/assets/source.png",
  "depth": "episodes/pilot-test/assets/depth.png",
  "out_dir": "episodes/pilot-test/renders",
  "name": "shot01",
  "mode": "layered",
  "n_layers": 5,
  "resolution": [1920, 1080],
  "fps": 24,
  "duration_s": 10,
  "depth_strength": 0.35,
  "camera": {"move": "push_in", "amplitude": 0.7, "sway": 0.03, "loop": false},
  "fog_density": 0.06
}
```

- `mode`: `"layered"` 또는 `"relief"`. **새로 쓰는 스펙은 반드시 명시한다. 권장값은 `layered`다.**
  - 필드가 없으면 v1 스펙으로 보고 `relief`로 해석한다(하위 호환). v1 스펙에는 레이어
    산출물이 없으므로 기본값을 `layered`로 두면 기존 샷의 결과가 조용히 바뀌기 때문이다.
- `n_layers`: layered 모드의 깊이 밴드 수(기본 3). relief 모드에서는 무시된다.
  - **실사/AI 생성 이미지에는 5를 권장한다.** 밴드가 적으면 하나의 물체가 밴드 경계에서
    찢어지고, 앞 레이어가 비켜설 때 드러나는 구멍이 커져 인페인팅 뭉갬이 눈에 띈다.
    파일럿 이미지를 amplitude 0.7 끝지점에서 비교했을 때 3은 아치 주변에 번짐이 보였고
    5는 거의 보이지 않았다.
- `depth_strength`: relief 모드의 평면 변위 크기(평면 폭 대비 비율 느낌으로 0.2~0.5 권장).
  layered 모드에서는 사용하지 않는다.
- `camera.amplitude`: 카메라가 다가가는 거리(블렌더 단위).
  - relief: 0.15~0.25. 크면 가장자리 왜곡이 드러난다.
  - layered: 0.5~0.9. 레이어 간 실제 시차가 생기므로 크게 움직여야 통과감이 난다.
- `camera.sway`: 좌우 흔들림 폭. `camera.loop`이 true면 모든 움직임이 사인 곡선으로
  시작점에 되돌아온다(두 모드 공통, 같은 수식).
- `fog_density`: 볼륨 안개 밀도. 0이면 안개 없음. layered 모드에서는 안개 볼륨이
  카메라와 최원경 평면 사이 전 구간을 덮도록 자동으로 늘어난다.

## layered 모드의 레이어 산출물

`render_shot`이 렌더 직전에 `pipeline.layers.split_layers`를 호출해 만든다(이미 있으면 재사용).

- 위치 규칙: `<image와 같은 디렉터리>/<image stem>_layers<n_layers>/layers.json`
  - 예: `assets/source.png`, `n_layers=3` → `assets/source_layers3/layers.json`
  - 이 규칙은 `pipeline/layers.py`의 `layers_json_path`와 `pipeline/blender/parallax_scene.py`의
    `layers_meta_path`에 **각각 구현돼 있다**. Blender의 파이썬에서는 numpy/cv2에 의존하는
    pipeline 패키지를 import할 수 없어 복제한 것이므로, 규칙을 바꾸면 두 곳을 함께 고쳐야 한다.
- 형식: `{"layers": [{"png": <절대경로>, "depth_qmid": <0..1>}, ...]}`, 가까운 레이어가 먼저.
- 전경·중경 PNG는 RGBA, 최원경 PNG는 구멍 없는 RGB.

## layered 모드의 배치 기하

- `depth_qmid`(1 = 가까움)를 카메라로부터의 거리 [1.6(가까움) .. 4.5(멂)]에 선형 매핑한다.
  단, 관측된 qmid 구간을 거리 구간 양 끝에 맞춰 늘린다(가장 가까운 레이어 = 1.6,
  최원경 = 4.5). 깊이맵 분포는 대개 멀리 쏠려 있어서 qmid를 0..1 그대로 대입하면
  거리 구간의 절반도 못 쓰고 시차가 눈에 띄지 않는다.
- 거리 d_i인 평면의 폭은 `w_i = w0 × (d_i / d0)`. d0/w0는 가장 가까운 레이어 기준이며,
  w0는 그 거리에서 프레임을 가로·세로 모두 덮는 폭에 여백 8%를 곱한 값이다.
  모든 평면에 같은 배율의 여백이 들어가므로 레이어 정합은 그대로고, 화면 가장자리만
  살짝 잘려 sway가 있어도 평면 끝이 프레임 안으로 들어오지 않는다.
- 이 규칙 때문에 카메라 시작 프레임에서는 모든 레이어가 원본 이미지와 동일하게 합성돼 보인다.
