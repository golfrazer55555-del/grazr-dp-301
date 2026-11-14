# GRAZR DP-301 — 3D 홍보 영상 (약 50초, 1920×1080, 24fps)

`3d-model/dp301_putter.blend`(최신 3D 모델)을 Blender Cycles로 렌더링하고, 문구·로고·음악을 합성해 만드는 영상입니다.
이전 `video/` 폴더의 사진 기반 영상과는 별개입니다.

## 구성 (음악 "Stairway"의 4마디 = 7.33초 단위로 컷)

| 시간 | 장면 | 문구 |
|---|---|---|
| 0.0–7.3 | 어둠 속에서 빛이 헤드 윤곽을 드러냄, 느린 푸시인 | PRECISION YOU CAN SEE / 한눈에 느껴지는 완성도 |
| 7.3–11.0 | 페이스 다이아몬드 밀링 매크로 | 100% FULL CNC MILLED / 헤드 전체를 초정밀 CNC로 깎아낸 정교한 밸런스와 일관된 반발력 |
| 11.0–14.7 | 바닥 각인(FORGED · STAINLESS SUS 304)이 보이도록 헤드 회전 | FORGED SUS304 STAINLESS / 부식에 강한 단조 SUS304, 묵직하면서도 부드러운 타구감 |
| 14.7–22.0 | 정면 슬로모션 스트로크, 16.49초 임팩트(음악을 낮추고 실제 타구음) | PURE, CRISP SOUND / 맑고 청량한 타구음 |
| 22.0–29.3 | 위에서 본 스트로크: 샤프트가 헤드 중앙, 헤드는 돌지 않고 공은 목표 라인을 따라 직진 | CENTER SHAFT / 헤드 뒤틀림은 줄이고, 직진성은 높이고 |
| 29.3–36.7 | 받침 없이 선 퍼터, 카메라가 돌아 뒤에서 목표 라인과 정렬을 내려다봄 | STANDS ON ITS OWN / 받침 없이 스스로 서고, 한 걸음 물러나 정렬을 확인 |
| 36.7–44.0 | 헤드를 공 위에 눌러 컷아웃에 끼우고 그대로 들어 올림 | PICKS UP THE BALL / 헤드로 공을 바로 집어 올립니다 |
| 44.0–49.7 | 곡의 마지막 타격음에 로고, 여운과 함께 페이드아웃 | 로고만 |

## 음악 편집
- 원곡 0.211초(첫 프레이즈)부터 44.155초까지 잔잔한 인트로 6프레이즈 + 161.283초(곡의 마지막 타격 직전)부터 끝까지.
  두 타격음 30ms 앞에서 잘라 박자가 그대로 이어지고, 로고가 곡의 자연스러운 끝과 함께 나옵니다.
- 16.49초 정면 임팩트: 음악을 약 -8dB 낮추고 `Putter-sound.m4a`를 정확히 맞춤. 23.82초 위에서 본 임팩트는 작게.

## 만들기
```bash
pip install bpy==5.3.0 pillow numpy
# 1) 3D 프레임 (프레임마다 시간 함수로 카메라/조명/스윙/공을 계산)
python3 video3d/scene.py --quality final --out video3d/frames            # 0000–1054.png, 약 7–8시간 (CPU)
python3 video3d/scene.py --shot stroke --quality final --out video3d/frames   # 장면 하나만 다시
python3 video3d/scene.py --stills 4.5,16.6 --quality draft --out /tmp/stills  # 특정 시점 스틸
# 2) 합성 (문구 + 로고 + 음악 + 타구음)
python3 video3d/compose.py --frames video3d/frames --out video3d/out/GRAZR_DP-301_film.mp4
```
- 품질: `preview`(960×540, 12샘플) / `draft`·`final`(1920×1080, 24샘플 + OIDN 노이즈 제거 — 48샘플과 차이 없음 확인)
- 렌더 프레임(`frames/`)은 용량이 커서 커밋하지 않습니다.

## 조명 / 화면 메모
- 완전한 검정 배경, 바닥은 아주 어두운 무광 + 8% 반사(카메라가 낮아도 바닥이 하얗게 뜨지 않음), 제품 주변만 보이고 멀어지면 검정으로 사라짐
- 림·탑·스윕 조명은 라이트 링킹으로 퍼터에만 닿게 해서 바닥에 번지지 않음
- 마지막 장면 뒤의 세로 빛기둥(배경 글로우)으로 검은 샤프트 실루엣을 살림

## 폰트 / 음원
- 문구: Montserrat Regular, Pretendard Light (`fonts/`, 둘 다 SIL Open Font License 1.1)
- 음악: "Stairway" — Patrick Patrikios (`audio/`). 사용 조건(라이선스)은 배포 전에 확인하세요.
