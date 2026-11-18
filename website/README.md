# GRAZR 웹사이트

DP-301 홍보 영상과 같은 검은 스튜디오 톤의 브랜드 사이트입니다. 한국어(`/`)와 영어(`/en/`, 소개만) 페이지가 있습니다.
구매는 네이버 스마트스토어로 연결하고, 사이트 직접 결제는 토스페이먼츠 승인 후에 붙입니다.

## 구성

| 경로 | 내용 |
|---|---|
| `public/` | Cloudflare가 그대로 서비스하는 완성본 (HTML은 `build.py`가 만듦) |
| `content.py` | 모든 문구, 가격, 옵션, 사업자 정보, 배송·반품, 상품정보 제공고시 |
| `legal.py` | 이용약관, 개인정보처리방침 (공정위 전자상거래 표준약관과 개인정보 보호법 항목 기준 초안) |
| `templates/` | 페이지 틀 (Jinja2) |
| `public/assets/css/site.css`, `public/assets/js/site.js` | 디자인과 동작 (스크롤 연출, 영상 재생, 3D 뷰어, 옵션 전환) |
| `tools/render_stills.py` | 33인치 실버 / 34인치 블랙 샤프트 제품 이미지 렌더 (Blender) |
| `tools/make_media.py` | 영상 프레임·사진·필름에서 사이트용 이미지와 짧은 영상 생성 → `public/media/` |
| `wrangler.jsonc` | Cloudflare 설정 (정적 사이트, `public/` 폴더) |

## 문구나 정보 바꾸기
```bash
pip install jinja2 fonttools brotli
python3 website/build.py
```
`content.py`에서 `None`으로 남은 값은 화면에 노란색 **확인 필요**로 표시됩니다(상호, 통신판매업 신고번호, 주소, 이메일, KC 인증정보, 약관 시행일).
도메인을 사면 `SITE_URL`에 넣고 다시 빌드하세요. 검색 노출 차단(noindex)이 풀리고 카카오톡 공유 미리보기, 사이트맵이 켜집니다.
한글 폰트(Pretendard)는 사이트에 쓰인 글자만 잘라서 넣으므로, 글을 바꾼 뒤에는 꼭 다시 빌드해야 합니다.

## 미디어 다시 만들기
```bash
python3 website/tools/render_stills.py --out website/.work/stills      # 샤프트 옵션 이미지 (약 1분)
python3 website/tools/make_media.py                                     # 전부 (영상 프레임 video3d/frames 필요)
python3 website/tools/make_media.py --only photos                       # 사진만
```

## Cloudflare에 올리기 (처음 한 번)
1. Cloudflare 대시보드 → **Workers & Pages** → **Create application** → **Import a repository** (GitHub 연결)
2. 저장소 `grazr-dp-301` 선택
3. 설정: Project name `grazr`, **Root directory** `website`, Build command 비움, Deploy command `npx wrangler deploy` (기본값)
4. 배포 브랜치(Settings → Builds → Production branch)를 `claude/grazer-dp301-putter-video-vkn9b1`로 지정
5. 배포가 끝나면 `grazr.<계정이름>.workers.dev` 주소가 생깁니다. 이후에는 브랜치에 올릴 때마다 자동 배포됩니다.

## 도메인 연결
- Cloudflare에서 산 도메인: Worker → **Settings → Domains & Routes → Add → Custom domain**에 도메인 입력
- 가비아에서 산 도메인: Cloudflare **Add a domain**으로 도메인 추가 → 안내되는 네임서버 2개를 가비아 **도메인 관리 → 네임서버 설정**에 입력 → 연결되면 위와 같이 Custom domain 추가

## 사이트 결제 (다음 단계)
도메인으로 사이트를 공개한 뒤 토스페이먼츠에 가입·심사 신청 → 승인 후 결제 화면과 결제 승인 처리(Worker)를 붙이고 `DIRECT_PAY = True`.
토스페이먼츠 비밀 키는 코드에 넣지 않고 Cloudflare 설정의 암호화된 변수로 넣습니다.

## 라이선스
Pretendard, Montserrat: SIL Open Font License 1.1 (`src/fonts/`) · model-viewer: Apache 2.0 (`public/assets/vendor/`)
필름 음악 "Stairway"(Patrick Patrikios)는 공개 전에 사용 조건을 확인하세요.
