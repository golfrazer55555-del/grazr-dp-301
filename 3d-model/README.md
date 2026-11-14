# GRAZR DP-301 — 3D 모델 (홍보용)

Blender(`bpy` 5.3)에서 Python 스크립트로 만든 모델입니다. 실측값은 `SPEC.md`에 정리돼 있고,
수치를 바꾼 뒤 스크립트를 다시 돌리면 모델·텍스처·렌더가 모두 새로 만들어집니다.

| 파일 | 내용 |
|---|---|
| `build_dp301.py` | 모델링 + 내보내기 + 렌더 스크립트 (치수 상수는 파일 상단) |
| `make_textures.py` | 그립 인쇄, 샤프트 로고, 로고 데칼 텍스처 생성 (`logo.png` 기반) |
| `dp301_putter.blend` | Blender 원본, 텍스처 포함 (헤드·무게추·샤프트·그립·데칼) |
| `dp301_putter.glb` | 웹 / AR / 다른 3D 툴용 (미터 단위, 텍스처 포함) |
| `dp301_head.stl` | 헤드 + 무게추, mm 단위 (형상 확인용) |
| `textures/` | 생성된 텍스처 |
| `renders/` | 스튜디오 렌더 9장 |
| `mass_report.txt` | SUS304 기준 계산 무게 |

## 반영한 스펙
- **헤드**: 폭(페이스 길이) 108 mm, 깊이 68 mm(무게추 포함), 높이 25 mm, 원통 날개 지름 25 mm,
  페이스 바 두께 14 mm, 볼 컷아웃 지름 42 mm, 로프트 3°, 라이 74°, 오른손잡이용, 순수 블랙 무광 코팅
- **페이스**: 다이아몬드 밀링(±32°, 다이아몬드 8.3 × 5.2 mm, 칸마다 가로 홈), 테두리 2 mm, 힐 쪽 흰색 GR 로고
  (밀링 홈도 같은 검은색 — 사진에서 밝게 보이는 건 빛 반사, 소유자 확인)
- **무게추**: 지름 25 mm × 두께 2 mm 폴리시드 SUS304, 톱니 6개 + 구멍 6개 + 원형 링 + 토크스 나사 (검정 각인)
- **바닥**: `head-bottom-taken straight up.png` 실측 배치 (GR 로고 높이 18 mm, GRAZR 44 × 7.8 mm, 문구 글자 높이 2.7 mm), 볼 컷아웃 지름 42 mm (공 42.67 mm가 끼워져 집히는 크기),
  웹·날개 안쪽 턱은 페이스에서 63.5 mm까지 (턱 뒤끝은 둥글게), 가공 결 간격 약 0.45 mm
- **바닥(이전)**: 정면 촬영 사진 기준 배치, 앞뒤 방향 CNC 가공 결, GR 로고, GRAZR, DP-301, `100%CNC MILLED / FORGED MODEL / STAINLESS / SUS 304`,
  `DUAL BALANCE / W.T/385g / LOFT/3° / LIE/74°`
- **뒷면**: 둥근 사각 포켓 2개 + GRAZR, 윗면 흰색 정렬선, 날개 안쪽 단차
- **샤프트**: 유광 블랙 그래파이트, 구경 9.4 mm(.370"), 센터 샤프트·논오프셋, 34", 호젤/페럴 없이 헤드에 바로 삽입.
  앞면: 그립 아래 약 70 mm에 GR 로고 / 뒷면: 그립 아래 165 mm부터 `DP-301 HIGH PERFORMANCE GRAPHITE / DESIGNED BY U.S.A. / S PUTTER FLEX`
- **그립**: 길이 270 mm, 지름 29 mm + 평평한 앞면 20 mm, 폴리우레탄 질감,
  대형 GR 헥사곤 로고·회색 패널 위 GRAZR·옆면 그래픽·`NON-SLIP`·`STANDARD 2.0`, 끝 캡 GR 엠보싱

## 렌더
`01_hero`, `02_face`, `03_top`, `04_back`, `05_sole`, `06_weights`, `07_grip`, `08_shaft`, `09_full`

## 다시 빌드
```bash
pip install bpy==5.3.0 pillow
python3 3d-model/build_dp301.py                       # 텍스처 + 내보내기 + 렌더 (96 샘플)
python3 3d-model/build_dp301.py --no-render           # 내보내기만
SAMPLES=256 ONLY=01_hero python3 3d-model/build_dp301.py   # 특정 컷만 고품질로
```

## 참고 / 추정한 부분
- 바닥 각인 폰트는 사진과 가장 비슷한 무료 폰트로 맞췄습니다: 문구 = Asap Condensed ExtraBold, `DP-301` = Montserrat Medium
  (`fonts/`, 둘 다 SIL Open Font License 1.1). 그 밖의 각인은 Inter, GR 로고와 GRAZR 워드마크는 `logo.png`에서 추출했습니다.
- 페이스 밀링 간격·깊이, 샤프트 인쇄 위치, 그립 그래픽 비율은 사진을 보고 추정했습니다.
- 무게: 보이는 외형 그대로 SUS304로 계산하면 헤드가 약 518 g으로 실제(385 g)보다 무겁습니다.
  실제 헤드에는 사진에 보이지 않는 내부 공간이 있는 것으로 보입니다. 홍보용 외형에는 영향이 없습니다.
