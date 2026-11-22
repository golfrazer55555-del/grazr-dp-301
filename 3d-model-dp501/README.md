# GRAZR DP-501 파크골프채 — 3D 모델 (홍보용)

Blender(`bpy` 5.3) Python 스크립트로 만든 모델입니다. 치수는 소유자 도면(`grazr dp-501 parkgolf photo/*-design.jpg`),
사진, KSPO 시험성적서 수치를 따릅니다. 성적서는 홍보에 쓸 수 없으므로 모델의 치수 근거로만 씁니다.

| 파일 | 내용 |
|---|---|
| `make_textures.py` | 도면에서 윗면 그래픽·헤드 윤곽을 뽑고, 옆면 문구·바닥 각인·샤프트 그래픽·카본·그립 텍스처를 만듦 |
| `build_dp501.py` | 모델링 + 내보내기 + 확인용 렌더 |
| `outline.json` | 윗면 윤곽(도면에서 추출), 샤프트 위치, 옆면 문구 위치 (mm) |
| `dp501_parkgolf.blend` / `.glb` | Blender 원본 / 웹·AR용 (미터 단위, 텍스처 포함) |
| `renders/` | 확인용 렌더 (히어로, 페이스, 윗면, 뒤, 바닥, 토우, 힐, 전체, 샤프트) |

## 반영한 스펙
- **헤드**: 말렛(D자형) 106 × 95 × 56 mm (높이는 성적서 실측, 도면의 53 mm는 규정 최소치), 윗면 모서리 챔퍼, 아래 모서리 라운드
- **재질/색**: 메이플 몸체에 피아노 블랙 도장 · 페이스 카본(평직) 7 mm + 황동 핀 4개 · 아래쪽 17.5 mm 황동 스커트와 바닥 · 뒤쪽 황동 무게추
- **윗면**: 도면의 금색·흰색 조준(별) 그래픽 그대로
- **옆면**: 힐 쪽 `GRAZR / GOLF RAZER`, 토우 쪽 `PARKER 300 UNIT / LIMITED EDITION` + 2색 GR 로고
- **바닥**: 헤어라인(앞뒤 방향) 황동, GR 로고·단풍잎 2개·GRAZR·`PREMIUM MAPLE TREE` 샌드 각인, 검정 `DP-501`
- **샤프트**: 지름 16 mm(헤드 쪽) 카본, 유광 블랙, 그립 아래 400–650 mm 구간 그래픽(GR 로고, GRAZR, 단풍잎, 조준선), 뒤 `PREMIUM MAPLE TREE`
  · 헤드 윗면 힐 쪽(X +12.9, Y 30 mm)으로 들어감, 힐 쪽으로 76° 기울기, 페이스 면과 평행(성적서 0°)
- **페럴**: 지름 20 mm 유광 블랙 + 금색 링
- **그립**: 350 mm 고무, 피라미드 패턴, 앞면 리브 패널, 금색 GRAZR·별, 끝 캡 GR 로고
- **전체 길이**: 85 cm (솔 면에서 그립 끝까지, 샤프트 축 기준)

## 다시 빌드
```bash
pip install bpy==5.3.0 pillow opencv-python-headless scipy
python3 3d-model-dp501/make_textures.py
python3 3d-model-dp501/build_dp501.py                  # 렌더까지 (SAMPLES=96)
python3 3d-model-dp501/build_dp501.py --no-render      # 내보내기만
```
