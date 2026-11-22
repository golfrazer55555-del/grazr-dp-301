# GRAZR DP-501 파크골프채 — 3D 모델

소유자 디자인 도안(윗면·옆면·바닥·샤프트)과 상세페이지 이미지를 기준으로 처음부터 다시 만든 모델입니다.
치수와 근거는 `SPEC.md`에 있습니다.

| 파일 | 내용 |
|---|---|
| `make_textures.py` | 도안에서 윗면 그래픽(위아래 대칭 복원), 바닥 단풍잎·DP-501을 추출하고, 옆면 글씨·샤프트 인쇄·그립·카본 직조 텍스처를 만듦 |
| `build_dp501.py` | 헤드·샤프트·페럴·그립 모델링, 재질, 렌더 |
| `compare_views.py` | 정사영 렌더 위에 도안 외곽선을 겹쳐 맞는지 확인 (`check/compare_*.jpg`) |
| `dp501_parkgolf.blend` | Blender 원본 |
| `renders/` | 확인용 렌더 |

## 헤드를 만드는 방법
윗면 도안의 외곽선 안쪽 각 점에서 외곽선까지의 거리 d를 구하고, 페이스 단면(상세페이지 페이스 사진과 실물 후면 사진에서
측정, 두 사진이 서로 일치)을 d의 함수로 써서 윗면·아랫면 높이를 정합니다. Y마다 단면을 옆면 도안의 위·아래 실루엣에
맞춰 늘리고 옮기므로, 윗면 도안·옆면 도안·앞뒤 단면이 동시에 맞습니다.

옆면 실루엣은 도안을 1픽셀 열마다 측정해 맞췄고(오차 rms 0.02~0.05 mm), 뒤쪽 황동 무게추의 모서리선은 끝까지 매끈하게
올라가도록 단면의 위·아래를 따로 늘립니다. 표면 법선은 삼각형이 아니라 곡면 식에서 직접 계산해 반사가 고르게 보입니다.

## 다시 빌드
```bash
pip install bpy==5.3.0 pillow opencv-python-headless scipy
python3 3d-model-dp501/make_textures.py
python3 3d-model-dp501/build_dp501.py                  # 확인용 렌더 10장
python3 3d-model-dp501/build_dp501.py --ortho          # 정사영 확인 뷰
python3 3d-model-dp501/build_dp501.py --site           # 웹사이트용 어두운 배경 이미지 (site/)
python3 3d-model-dp501/compare_views.py                # 도안과 겹쳐 보기
```
