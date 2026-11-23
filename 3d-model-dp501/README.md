# GRAZR DP-501 파크골프채 — 3D 모델

소유자 디자인 도안(윗면·옆면·바닥·샤프트)과 소유자가 보낸 실물 사진을 기준으로 만든 모델입니다. 치수와 근거는 `SPEC.md`에
있습니다.

| 파일 | 내용 |
|---|---|
| `dp501_shape.py` | 헤드 형태 (numpy만 사용): 평면 윤곽, 옆 실루엣, 주름 단면의 각 면과 이음 |
| `make_textures.py` | 윗면 그래픽, 바닥 각인, 옆면 글씨, 샤프트 인쇄, 그립, 카본 직조 텍스처 |
| `build_dp501.py` | 헤드·샤프트·페럴·그립 모델링, 재질, 렌더 |
| `compare_views.py` | 정사영 렌더 위에 도안 외곽선을 겹쳐 확인 (`check/compare_*.jpg`) |
| `check/photo_cams.json` | 소유자 사진(140 페이스, 141 바닥, 146 뒷면)에서 역산한 카메라 |
| `dp501_parkgolf.blend` | Blender 원본 |
| `renders/` | 확인용 렌더 10장 |

## 헤드를 만드는 방법
평면 윤곽 안의 각 점에서 윤곽까지의 거리 d를 구하고, 단면의 각 면을 d나 X·Y의 함수로 정합니다: 윗 경사면은 가장 넓은
선에서 일정한 기울기로 올라가고, 옆벽은 일정한 기울기로 내려가며, 크라운·바닥은 옆면 도안의 실루엣을 따릅니다. 면과 면은
2차 미분까지 연속인 smooth min / max로 이어서 주름선이 또렷하면서도 반사가 고르게 보입니다. 메쉬는 주름선에 맞춰
나누고, 법선은 같은 식에서 직접 계산합니다.

뒷면의 주름선과 황동 경계는 소유자 사진에서 역산한 카메라로 모델 선을 사진 위에 겹쳐 맞췄습니다. 페이스 카본 무늬는
페이스 사진을 그 카메라로 펴서 직조 격자로 접어 평균한 명암(`textures/carbon_photo_tile.png`)을 씁니다.

## 다시 빌드
```bash
pip install bpy==5.3.0 pillow opencv-python-headless scipy
python3 3d-model-dp501/make_textures.py
python3 3d-model-dp501/build_dp501.py                  # 확인용 렌더 10장
python3 3d-model-dp501/build_dp501.py --match          # 소유자 사진과 같은 카메라 (check/match_*.png)
python3 3d-model-dp501/build_dp501.py --photo          # 사진 비슷한 각도 (check/photo_*.png)
python3 3d-model-dp501/build_dp501.py --ortho          # 정사영 확인 뷰
python3 3d-model-dp501/build_dp501.py --site           # 웹사이트용 어두운 배경 이미지 (site/)
python3 3d-model-dp501/compare_views.py                # 도안과 겹쳐 보기
```
