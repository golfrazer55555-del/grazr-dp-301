# GRAZR DP-501 — 3D 홍보 영상 (약 51초, 1920×1080, 24fps)

`3d-model-dp501/dp501_parkgolf.blend`(승인된 3D 모델)을 Blender Cycles로 렌더링하고, 문구·로고·음악을 합성해 만드는 영상입니다.
DP-301 영상(`video3d/`)과 같은 방식입니다.

## 음악
"Flower Duet" (들리브 「라크메」) — Golden Cut Reborn 연주, 유튜브 오디오 보관함
(수익 창출 동영상 포함 모든 동영상에 사용 가능, 저작자 표시 필요 없음. 음원 파일만 따로 배포하는 것은 안 됨).

- 박자: 8분음표 기준 약 117 BPM (조금씩 흔들림). 16박(약 7.5–7.7초)을 한 구절로 보고 장면을 나눕니다.
- 편집: 곡 첫 음(0.441초)부터 43.456초(90번째 박)까지, 이어서 곡의 마지막 부분 153.379초부터 끝(161.2초)까지.
  두 지점 모두 박 30ms 앞에서 자르고, 자르기 전 8박의 화성이 가장 비슷한 곳(크로마 유사도 0.83)을 골라 이음새가 들리지 않게 했습니다.

## 구성

| 영상 시간 | 장면 | 문구 |
|---|---|---|
| 0.0–7.4 | 어둠 속에서 빛이 메이플 헤드를 드러냄, 토우·앞쪽에서 천천히 다가감 | PREMIUM MAPLE TREE / 300개 한정 프리미엄 파크골프채 |
| 7.4–11.1 | 카본 페이스를 따라 미끄러지는 접사 (직조 무늬와 황동 핀) | FULL CARBON FACE / 풀 카본 페이스, 부드러운 타구감 |
| 11.1–14.9 | 토우 쪽 PARKER 300 UNIT LIMITED EDITION, 빛이 지나감 | LIMITED TO 300 / 단 300개만 만든 한정판 |
| 14.9–22.5 | 뒤쪽을 천천히 돌며 황동추 | REAR BRASS WEIGHT / 후면 황동추, 낮고 깊은 무게중심 |
| 22.5–30.2 | 헤드를 뒤집어 황동 바닥, 금 글리터 각인이 빛에 반짝임 | GOLD-ENGRAVED BRASS SOLE / 금빛 각인을 새긴 황동 바닥 |
| 30.2–37.9 | 샤프트 인쇄를 따라 내려와 헤드 윗면 조준 그래픽 | MAPLE AIMING LINE / 헤드와 샤프트의 조준 라인으로 정확하게 |
| 37.9–43.0 | 옆에서 본 스윙: 어드레스, 백스윙, 41.0초 박자에 임팩트, 공이 굴러감 | EASIER, MORE PRECISE / 더 쉽게, 더 정교하게 |
| 43.0–47.2 | 곡의 마무리 구절: 선 클럽 주위를 돌며 힐 쪽 GRAZR | CERTIFIED CLUB / (사)대한파크골프협회 공인인증 |
| 47.2–50.8 | 로고, 아래에 DP-501 · PARK GOLF, 여운과 함께 페이드아웃 | — |

## 만들기
```bash
pip install bpy==5.3.0 pillow numpy
python3 video501/scene.py --quality final --out video501/frames                 # 0000–1132.png (CPU, 수 시간)
python3 video501/scene.py --shot sole --quality final --out video501/frames     # 장면 하나만 다시
python3 video501/scene.py --stills 5.5,18.5 --quality preview --out /tmp/stills # 특정 시점 스틸
python3 video501/compose.py --frames video501/frames --out video501/out/GRAZR_DP-501_film.mp4
```
- 품질: `preview`(960×540, 12샘플) / `final`(1920×1080, 24샘플 + OIDN 노이즈 제거)
- 렌더 프레임(`frames/`)은 용량이 커서 커밋하지 않습니다.
- 문구 폰트: Montserrat, Pretendard (`fonts/`, SIL Open Font License 1.1)
