"""All website text and facts in one place. Edit here, then run `python3 website/build.py`.

None = not provided yet: the page shows a visible "확인 필요" marker in its place.
"""

SITE_URL = "https://grazr.co.kr"
STORE_URL = "https://smartstore.naver.com/duddy/products/11585263659"
YOUTUBE_URL = "https://www.youtube.com/@GRAZR-OFFICIAL"
INSTAGRAM_URL = "https://www.instagram.com/grazr.official/"
KAKAO_URL = "https://pf.kakao.com/_DFdvX"            # 카카오톡 채널 홈
KAKAO_CHAT_URL = "https://pf.kakao.com/_DFdvX/chat"  # 1:1 채팅 바로 열기
PRICE_KRW = 385000
STORE_PRICE_301 = 425000    # 네이버 스마트스토어 판매가 (사이트 결제가 더 저렴)
SHOW_DP501 = True          # two-product site (home + /dp-301/ + /dp-501/); off until the DP-501 page is finished
DIRECT_PAY = True          # show the "사이트에서 바로 결제" button on the home page (after Toss approval)
# Toss Payments (결제위젯). "test" = no real charge; switch to "live" with the live client key after approval
# and set the live secret key as the Cloudflare secret TOSS_SECRET_KEY (never in this file).
PAY_MODE = "live"
TOSS_CLIENT_KEY = "live_gck_c19zorA9SpFACqnxWJmfGDQguN0UkIlZYs"   # 아이엔골프 결제위젯 라이브 클라이언트 키 (public)

BUSINESS = {
    "name": "아이엔골프",                # 상호
    "ceo": "도종규",                    # 대표자
    "biz_no": "502-19-73146",          # 사업자등록번호
    "mail_order_no": "2023-대구동구-0720",  # 통신판매업 신고번호
    "address": "대구광역시 동구 안심로 389-3, A동 111호(신서동, 제이에스의류관)",  # 사업장 주소 (사업자등록증과 동일)
    "phone": "053-962-5531",
    "phone_intl": "+82-53-962-5531",
    "email": "grazrofficial@gmail.com",
    "hosting": "Cloudflare, Inc.",     # 호스팅 서비스 제공자 (전자상거래법 표시 사항)
    "privacy_officer": "도종규 (대표)",  # 개인정보 보호책임자
}

# 배송·교환·반품 (스마트스토어 상품정보 제공고시 / 반품·교환 안내와 동일)
SHIPPING = {
    "fee": "무료",
    "courier": "로젠택배",
    "dispatch": "결제 후 1일 이내 발송",
    "return_fee": "편도 8,000원 (처음 배송비가 무료였던 경우 16,000원)",
    "exchange_fee": "16,000원",
    "return_address": "(41083) 대구광역시 동구 안심로 389-3, A동 111호(신서동, 제이에스의류관)",
    "as_phone": "053-962-5531",
}

# 상품정보 제공고시 (전자상거래법) - 스마트스토어 등록 내용 기준
NOTICE = [
    ("품명 / 모델명", "프리미엄 FULL CNC 고급 퍼터 / DP-301"),
    ("KC 인증정보", "해당 없음"),
    ("크기", "헤드 가로 108mm × 세로 68mm × 높이 25mm, 길이 33인치 / 34인치"),
    ("중량", "헤드 385g"),
    ("색상", "헤드 블랙, 샤프트 실버(33인치) / 블랙(34인치)"),
    ("재질", "헤드 단조 SUS304 스테인리스, 샤프트 그라파이트"),
    ("제품 구성", "퍼터, 헤드커버"),
    ("동일 모델의 출시연월", "2023년"),
    ("제조자", "아이엔골프 (OEM 생산)"),
    ("수입자", "지브이투어"),
    ("제조국", "중국"),
    ("품질보증기준", "관련 법령 및 소비자분쟁해결기준(공정거래위원회 고시)에 따릅니다."),
    ("A/S 책임자와 전화번호", "053-962-5531"),
]
TERMS_EFFECTIVE = "2026년 11월 19일"     # 시행일 (사이트 공개일)

# shaft options (same price)
OPTIONS = [
    {"key": "black", "inch": 34, "img": "full-black", "head": "head-black"},
    {"key": "silver", "inch": 33, "img": "full-silver", "head": "head-silver"},
]

KO = {
    "lang": "ko",
    "title": "GRAZR DP-301 | 헤드 전체를 깎아 만든 퍼터",
    "description": "단조 SUS304 헤드를 100% CNC로 깎아 만든 GRAZR DP-301 퍼터. 다이아몬드 밀링 페이스, 센터 샤프트, "
                   "받침 없이 서는 헤드, 헤드로 공을 집어 올리는 컷아웃.",
    "nav": [("기능", "#features"), ("3D", "#view3d"), ("사양", "#specs"), ("구매", "#buy")],
    "nav_cta": ("구매하기", "#buy"),
    "lang_switch": ("EN", "/en/"),
    "hero_eyebrow": "GRAZR DP-301",
    "hero_title": "PRECISION <br class=\"br-m\">YOU CAN SEE",
    "hero_sub": "한눈에 느껴지는 완성도",
    "hero_buttons": [("구매하기", "#buy", "primary"), ("영상 보기", "#film", "ghost")],
    "scroll_hint": "SCROLL",
    "intro_title": "헤드 전체를 깎아 만든 퍼터",
    "intro_text": "단조 SUS304 스테인리스를 초정밀 CNC로 깎아 헤드를 완성했습니다. 페이스에는 다이아몬드 패턴을 새기고, "
                  "샤프트는 헤드 정중앙에 꽂았습니다. 받침 없이 스스로 서고, 헤드로 공을 집어 올립니다.",
    "features": [
        {"id": "milling", "en": "100% FULL CNC MILLED", "title": "헤드 전체를 깎아낸 정밀함",
         "text": "헤드 전체를 초정밀 CNC로 깎아낸 정교한 밸런스와 일관된 반발력. 페이스 전면에는 다이아몬드 패턴 밀링을 새겼습니다."},
        {"id": "forged", "en": "FORGED SUS304 STAINLESS", "title": "단조 SUS304 스테인리스",
         "text": "부식에 강한 단조 SUS304로 만들었습니다. 묵직하면서도 부드러운 타구감을 느껴 보세요."},
        {"id": "sound", "en": "PURE, CRISP SOUND", "title": "맑고 청량한 타구음",
         "text": "단단한 단조 헤드와 밀링 페이스가 만드는 소리입니다. 소리를 켜고 들어 보세요.",
         "sound_button": "타구음 듣기", "sound_playing": "재생 중"},
        {"id": "center", "en": "CENTER SHAFT", "title": "헤드 정중앙의 샤프트",
         "text": "샤프트가 헤드 정중앙에 꽂혀 있습니다. 헤드 뒤틀림은 줄이고, 직진성은 높였습니다."},
        {"id": "stand", "en": "STANDS ON ITS OWN", "title": "받침 없이 혼자 섭니다",
         "text": "평평한 곳에 내려놓으면 받침 없이 스스로 섭니다. 퍼터를 세워 두고 한 걸음 물러나 정렬을 확인해 보세요."},
        {"id": "pickup", "en": "PICKS UP THE BALL", "title": "헤드로 공을 집어 올립니다",
         "text": "헤드 가운데의 지름 42mm 컷아웃을 공 위에 대고 살짝 누르면 공이 끼워집니다. 그대로 들어 올리면 되니 허리를 숙일 필요가 없습니다."},
    ],
    "replay": "다시 보기",
    "v3d_eyebrow": "3D VIEW",
    "v3d_title": "직접 돌려 보세요",
    "v3d_text": "드래그해서 돌리고, 두 손가락이나 휠로 확대할 수 있습니다. 휴대폰에서는 AR로 내 공간에 실제 크기로 세워 볼 수 있습니다.",
    "v3d_load": "3D로 보기",
    "v3d_loading": "불러오는 중",
    "v3d_ar": "내 공간에서 보기 (AR)",
    "v3d_hint": "3D 모델은 약 5MB입니다. 버튼을 누르면 불러옵니다.",
    "shaft_label": "샤프트",
    "opt_short": {"black": "34인치 · 블랙", "silver": "33인치 · 실버"},
    "opt_long": {"black": "34인치 · 블랙 샤프트", "silver": "33인치 · 실버 샤프트"},
    "photos_eyebrow": "REAL PHOTOS",
    "photos_title": "실물 사진",
    "photos_text": "렌더가 아닌 실제 제품 사진입니다.",
    "photos": [
        ("face", "다이아몬드 밀링 페이스"),
        ("sole", "바닥 각인"),
        ("pickup-back", "공을 집어 올린 모습"),
        ("pickup-top", "컷아웃에 끼워진 공"),
        ("back", "후면 듀얼 무게추"),
        ("weight", "무게추 디테일"),
        ("cover", "전용 헤드커버"),
        ("grip", "GRAZR 그립"),
        ("shaft", "그라파이트 샤프트"),
    ],
    "film_eyebrow": "FILM",
    "film_title": "GRAZR DP-301 필름",
    "film_play": "영상 재생",
    "specs_eyebrow": "SPECIFICATIONS",
    "specs_title": "사양",
    "specs": [
        ("모델", "GRAZR DP-301"),
        ("헤드 소재", "단조 SUS304 스테인리스"),
        ("가공", "헤드 전체 100% CNC 밀링, 다이아몬드 패턴 페이스"),
        ("헤드 무게", "385g"),
        ("로프트", "3°"),
        ("라이", "74°"),
        ("길이", "33인치 / 34인치"),
        ("샤프트", "그라파이트 (33인치 실버, 34인치 블랙)"),
        ("샤프트 위치", "센터 샤프트, 논오프셋"),
        ("무게추", "후면 듀얼 무게추 (DUAL BALANCE)"),
        ("헤드 크기", "가로 108mm × 세로 68mm × 높이 25mm"),
        ("볼 픽업", "지름 42mm 컷아웃"),
        ("그립", "GRAZR 기본 그립"),
        ("구성", "퍼터, 전용 헤드커버"),
        ("방향", "오른손용"),
        ("제조사", "아이엔골프 (OEM 생산)"),
        ("수입자", "지브이투어"),
        ("제조국", "중국"),
    ],
    "buy_eyebrow": "ORDER",
    "buy_title": "GRAZR DP-301",
    "price": "385,000원",
    "buy_option_label": "길이 · 샤프트",
    "buy_same_price": "두 길이 모두 같은 가격입니다.",
    "buy_includes": "구성: 퍼터 + 전용 헤드커버 · 오른손용",
    "buy_store": "네이버 스마트스토어에서 구매",
    "buy_direct_note": "신용·체크카드, 간편결제 · 토스페이먼츠 안전결제",
    "buy_direct": "사이트에서 바로 결제",
    "buy_direct_soon": "사이트 결제는 준비 중입니다.",
    "buy_note": "스마트스토어 판매가는 425,000원입니다. 배송·교환 조건은 같습니다.",
    "faq_eyebrow": "FAQ",
    "faq_title": "자주 묻는 질문",
    "faq": [
        ("33인치와 34인치는 무엇이 다른가요?",
         "길이와 샤프트 색이 다릅니다. 33인치는 실버, 34인치는 블랙 샤프트이고, 헤드와 가격은 같습니다."),
        ("왼손잡이용이 있나요?", "현재는 오른손용만 있습니다."),
        ("헤드커버가 함께 오나요?", "네, 전용 헤드커버가 함께 들어 있습니다."),
        ("무게추를 바꿀 수 있나요?",
         "후면 무게추는 렌치로 풀고 끼울 수 있습니다. 다만 다른 무게의 교체용 무게추는 따로 판매하지 않습니다."),
        ("정말 혼자 서나요?",
         "평평한 바닥에서는 받침 없이 스스로 섭니다. 경사가 있거나 고르지 않은 곳에서는 넘어질 수 있습니다."),
        ("공은 어떻게 집나요?",
         "헤드 가운데 컷아웃을 공 위에 대고 살짝 누르면 공이 끼워집니다. 그대로 들어 올리면 됩니다."),
        ("어디서 살 수 있나요?",
         "이 페이지에서 바로 결제하시거나 네이버 스마트스토어에서 구매하실 수 있습니다. 사이트에서 바로 결제하시면 385,000원, 스마트스토어는 425,000원입니다. 배송·교환 조건은 같습니다."),
        ("배송은 얼마나 걸리나요?", "배송비는 무료이며, 로젠택배로 결제 후 1일 이내에 발송합니다."),
        ("교환·반품은 어떻게 하나요?",
         "상품을 받은 날부터 7일 이내에 신청하실 수 있습니다. 단순 변심일 때 반품 배송비는 편도 8,000원"
         "(처음 배송비가 무료였던 경우 16,000원), 교환 배송비는 16,000원입니다. 상품 하자나 오배송은 판매자가 배송비를 부담합니다. "
         "자세한 기준은 이용약관을 확인해 주세요."),
    ],
    "footer_terms": ("이용약관", "/terms/"),
    "footer_privacy": ("개인정보처리방침", "/privacy/"),
    "biz_labels": {"name": "상호", "ceo": "대표자", "biz_no": "사업자등록번호", "mail_order_no": "통신판매업 신고번호",
                   "address": "주소", "phone": "전화", "email": "이메일", "hosting": "호스팅 제공자"},
    "todo": "확인 필요",
    "youtube": "유튜브",
    "kakao": "카카오톡 채널",
    "instagram": "인스타그램",
    "kakao_chat": "카카오톡 상담",
    "kakao_ask": "궁금한 점은 카카오톡으로 물어보세요",
}

EN = {
    "lang": "en",
    "title": "GRAZR DP-301 Putter | Precision You Can See",
    "description": "GRAZR DP-301: a 100% CNC-milled putter in forged SUS304 stainless steel, with a diamond-milled face, "
                   "a center shaft, a head that stands on its own and a cutout that picks up the ball.",
    "nav": [("Features", "#features"), ("3D", "#view3d"), ("Specs", "#specs")],
    "nav_cta": ("Watch film", "#film"),
    "lang_switch": ("한국어", "/dp-301/" if SHOW_DP501 else "/"),
    "hero_eyebrow": "GRAZR DP-301",
    "hero_title": "PRECISION <br class=\"br-m\">YOU CAN SEE",
    "hero_sub": "Milled from end to end",
    "hero_buttons": [("Watch film", "#film", "primary"), ("Specs", "#specs", "ghost")],
    "scroll_hint": "SCROLL",
    "intro_title": "A putter milled from end to end",
    "intro_text": "The whole head is precision CNC-milled from forged SUS304 stainless steel. A diamond pattern is milled "
                  "across the face and the shaft sits at the exact centre. It stands on its own, and its head picks up the ball.",
    "features": [
        {"id": "milling", "en": "100% FULL CNC MILLED", "title": "Milled, every surface",
         "text": "Every surface of the head is precision CNC-milled for refined balance and a consistent response. "
                 "A diamond pattern is milled across the full face."},
        {"id": "forged", "en": "FORGED SUS304 STAINLESS", "title": "Forged stainless steel",
         "text": "Forged from corrosion-resistant SUS304 stainless steel, for a solid yet soft feel."},
        {"id": "sound", "en": "PURE, CRISP SOUND", "title": "A clean, crisp sound",
         "text": "The sound of a forged head and a milled face. Turn your sound on and listen.",
         "sound_button": "Play the sound", "sound_playing": "Playing"},
        {"id": "center", "en": "CENTER SHAFT", "title": "Shaft at the centre",
         "text": "The shaft enters the exact centre of the head, reducing twist and keeping the ball on line."},
        {"id": "stand", "en": "STANDS ON ITS OWN", "title": "It stands on its own",
         "text": "Set it down on a flat surface and it stands by itself, so you can step back and check your alignment."},
        {"id": "pickup", "en": "PICKS UP THE BALL", "title": "Picks up the ball",
         "text": "Press the 42 mm cutout over the ball and it clicks in. Lift it straight up, with no bending down."},
    ],
    "replay": "Replay",
    "v3d_eyebrow": "3D VIEW",
    "v3d_title": "Turn it in your hands",
    "v3d_text": "Drag to rotate, pinch or scroll to zoom. On a phone, place it at real size in your room with AR.",
    "v3d_load": "View in 3D",
    "v3d_loading": "Loading",
    "v3d_ar": "View in your space (AR)",
    "v3d_hint": "The 3D model is about 5 MB and loads when you press the button.",
    "shaft_label": "Shaft",
    "opt_short": {"black": "34\" · Black", "silver": "33\" · Silver"},
    "opt_long": {"black": "34 inch · black shaft", "silver": "33 inch · silver shaft"},
    "photos_eyebrow": "REAL PHOTOS",
    "photos_title": "The real thing",
    "photos_text": "Photographs of the actual putter, not renders.",
    "photos": [
        ("face", "Diamond-milled face"),
        ("sole", "Sole engraving"),
        ("pickup-back", "Ball picked up"),
        ("pickup-top", "Ball held in the cutout"),
        ("back", "Dual rear weights"),
        ("weight", "Weight detail"),
        ("cover", "Head cover"),
        ("grip", "GRAZR grip"),
        ("shaft", "Graphite shaft"),
    ],
    "film_eyebrow": "FILM",
    "film_title": "GRAZR DP-301 film",
    "film_play": "Play film",
    "specs_eyebrow": "SPECIFICATIONS",
    "specs_title": "Specifications",
    "specs": [
        ("Model", "GRAZR DP-301"),
        ("Head material", "Forged SUS304 stainless steel"),
        ("Machining", "100% CNC-milled head, diamond-pattern face"),
        ("Head weight", "385 g"),
        ("Loft", "3°"),
        ("Lie", "74°"),
        ("Length", "33\" / 34\""),
        ("Shaft", "Graphite (33\" silver, 34\" black)"),
        ("Hosel", "Center shaft, no offset"),
        ("Weights", "Dual rear weights (DUAL BALANCE)"),
        ("Head size", "108 × 68 × 25 mm"),
        ("Ball pick-up", "42 mm cutout"),
        ("Grip", "GRAZR standard grip"),
        ("In the box", "Putter, head cover"),
        ("Hand", "Right-handed"),
        ("Made in", "China"),
    ],
    "avail_eyebrow": "AVAILABILITY",
    "avail_title": "Sold in Korea",
    "avail_text": "GRAZR DP-301 is currently sold in Korea only. International orders are not available yet.",
    "faq_eyebrow": "FAQ",
    "faq_title": "Questions",
    "faq": [
        ("What is the difference between 33\" and 34\"?",
         "Length and shaft colour: the 33\" has a silver shaft and the 34\" a black one. The head and price are the same."),
        ("Is there a left-handed model?", "Not at the moment. It is right-handed only."),
        ("Does it come with a head cover?", "Yes, a GRAZR head cover is included."),
        ("Can I change the weights?",
         "The rear weights can be removed with a wrench, but no alternative weights are sold."),
        ("Does it really stand on its own?",
         "Yes, on a flat surface. On a slope or uneven ground it can fall over."),
        ("Do you ship internationally?", "Not yet. It is currently sold in Korea only."),
    ],
    "footer_terms": ("Terms (Korean)", "/terms/"),
    "footer_privacy": ("Privacy (Korean)", "/privacy/"),
    "biz_labels": {"name": "Company", "ceo": "CEO", "biz_no": "Business reg. no.", "mail_order_no": "Mail-order reg. no.",
                   "address": "Address", "phone": "Tel", "email": "Email", "hosting": "Hosting"},
    "todo": "TBD",
    "youtube": "YouTube",
    "kakao": "KakaoTalk",
    "instagram": "Instagram",
    "kakao_chat": "Chat on KakaoTalk",
    "kakao_ask": "Questions? Chat with us on KakaoTalk",
}

# ================================================================ DP-501 park golf club
STORE_URL_501 = "https://naver.me/FlBXUTu6"
PRICE_501 = 460000
STORE_PRICE_501 = 510000    # 네이버 스마트스토어 판매가
NOTICE_501 = [
    ("품명 / 모델명", "파크골프채 / GRAZR DP-501"),
    ("KC 인증정보", "해당 없음"),
    ("크기", "길이 85cm, 헤드 가로 106mm × 세로 95mm × 높이 56mm"),
    ("중량", "530g 내외"),
    ("색상", "블랙 · 골드"),
    ("재질", "헤드 단풍나무(메이플) 원목 · 황동 · 카본 페이스, 샤프트 카본, 그립 고무"),
    ("제품 구성", "파크골프채, 전용 헤드커버"),
    ("동일 모델의 출시연월", "2024년 1월"),
    ("제조자", "아이엔골프 (OEM 생산)"),
    ("수입자", "지브이투어"),
    ("제조국", "중국"),
    ("품질보증기준", "관련 법령 및 소비자분쟁해결기준(공정거래위원회 고시)에 따릅니다."),
    ("A/S 책임자와 전화번호", "053-962-5531"),
]
P501 = {
    "key": "dp-501",
    "title": "GRAZR DP-501 파크골프채 | 300개 한정 프리미엄 메이플",
    "description": "최고급 단풍나무 원목 헤드에 후면 황동추, 풀 카본 페이스. (사)대한파크골프협회 공인인증 클럽 "
                   "GRAZR DP-501, 300개 한정판.",
    "nav": [("특징", "#features"), ("3D", "#view3d"), ("사양", "#specs"), ("구매", "#buy")],
    "hero_eyebrow": "GRAZR DP-501 · PARK GOLF",
    "hero_title": "PREMIUM <br class=\"br-m\">MAPLE TREE",
    "hero_sub": "300개 한정 프리미엄 파크골프채",
    "hero_buttons": [("구매하기", "#buy", "primary"), ("특징 보기", "#features", "ghost")],
    "limited": "PARKER 300 UNIT LIMITED EDITION",
    "intro_title": "부드러운 타구감, 더 쉽게 더 정교하게",
    "intro_text": "최고급 단풍나무 원목 헤드에 황동추와 풀 카본 페이스를 더했습니다. 협회 규정 안에서 헤드와 샤프트를 "
                  "가장 크고 두껍게 만들어, 초보자부터 중·상급자, 선수용까지 편하게 칠 수 있습니다.",
    "features": [
        {"id": "brass", "en": "REAR BRASS WEIGHT", "title": "후면 황동추, 낮고 깊은 무게중심",
         "text": "헤드 뒤쪽에 황동 무게추를 달아 무게중심을 뒤로 옮겼습니다. 공을 쉽게 띄우고 멀리 보내며, "
                 "빗맞았을 때 손에 전해지는 진동을 줄여 줍니다."},
        {"id": "maple", "en": "MAXIMUM MAPLE HEAD", "title": "공인 허용치 최대 크기의 메이플 헤드",
         "text": "협회 규정 안에서 헤드를 가장 크게 키워 스윗스팟을 넓혔습니다. 미스샷 부담이 줄어 초보자부터 상급자까지 편하게 칩니다."},
        {"id": "shaft", "en": "HIGH-MODULUS CARBON SHAFT", "title": "공인 허용치 최대 두께의 카본 샤프트",
         "text": "일반 클럽보다 두껍고 탄성이 좋은 고탄성 카본 샤프트입니다. 스윙할 때 뒤틀림을 억제하고 내구성과 비거리를 높였습니다."},
        {"id": "aim", "en": "MAPLE AIMING LINE", "title": "단풍나무 조준 라인",
         "text": "헤드 윗면과 샤프트에 정렬 라인을 넣었습니다. 어드레스할 때 목표 방향으로 정확하게 맞출 수 있습니다."},
    ],
    "cert_eyebrow": "CERTIFIED",
    "cert_title": "(사)대한파크골프협회 공인인증 클럽",
    "cert_text": "대회에서도 그대로 쓸 수 있는 공인 클럽입니다. 클럽에 협회 공인인증 스티커가 붙어 있습니다.",
    "v3d_title": "직접 돌려 보세요",
    "v3d_hint": "3D 모델은 약 3MB입니다. 버튼을 누르면 불러옵니다.",
    "photos": [
        ("face", "풀 카본 페이스와 황동 핀"),
        ("top", "윗면 조준 그래픽"),
        ("sole", "황동 바닥 각인"),
        ("back", "후면 황동 무게추"),
        ("toe", "PARKER 300 UNIT LIMITED EDITION"),
        ("heel", "GRAZR GOLF RAZER"),
        ("shaft", "카본 샤프트 그래픽"),
        ("grip", "미끄럼 방지 고무 그립"),
        ("cover", "전용 헤드커버"),
    ],
    "specs": [
        ("모델", "GRAZR DP-501"),
        ("종류", "파크골프채 · 말렛형 헤드"),
        ("헤드", "최고급 단풍나무(메이플) 원목 + 후면 황동추"),
        ("페이스", "풀 카본"),
        ("바닥", "황동 (각인)"),
        ("헤드 크기", "가로 106mm × 세로 95mm × 높이 56mm"),
        ("샤프트", "고탄성 카본 (공인 규정 허용치 내 최대 두께)"),
        ("그립", "미끄럼 방지 고무 그립"),
        ("길이", "85cm"),
        ("총 무게", "530g 내외"),
        ("방향", "오른손용"),
        ("공인", "(사)대한파크골프협회 공인인증"),
        ("수량", "300개 한정 (PARKER 300 UNIT LIMITED EDITION)"),
        ("구성", "파크골프채, 전용 고급 헤드커버"),
        ("제조사", "아이엔골프 (OEM 생산)"),
        ("수입자", "지브이투어"),
        ("제조국", "중국"),
    ],
    "price": "460,000원",
    "buy_option": "85cm · 오른손용",
    "buy_includes": "구성: 파크골프채 + 전용 고급 헤드커버 · 오른손용",
    "buy_note": "스마트스토어 판매가는 510,000원입니다. 배송·교환 조건은 같습니다.",
    "faq": [
        ("대회에서 쓸 수 있나요?", "네, (사)대한파크골프협회 공인인증 클럽입니다. 클럽에 공인인증 스티커가 붙어 있습니다."),
        ("길이와 무게는 어떻게 되나요?", "길이 85cm, 총 무게 530g 내외입니다. 길이는 한 가지입니다."),
        ("왼손잡이용이 있나요?", "현재는 오른손용만 있습니다."),
        ("정말 300개만 판매하나요?", "네, 300개 한정판입니다. 헤드 옆면에 PARKER 300 UNIT LIMITED EDITION이 새겨져 있습니다."),
        ("헤드커버가 함께 오나요?", "네, 전용 고급 헤드커버가 함께 들어 있습니다."),
        ("어디서 살 수 있나요?",
         "이 페이지에서 바로 결제하시거나 네이버 스마트스토어에서 구매하실 수 있습니다. 사이트에서 바로 결제하시면 460,000원, 스마트스토어는 510,000원입니다. 배송·교환 조건은 같습니다."),
        ("배송은 얼마나 걸리나요?", "배송비는 무료이며, 로젠택배로 결제 후 1일 이내에 발송합니다."),
        ("교환·반품은 어떻게 하나요?",
         "상품을 받은 날부터 7일 이내에 신청하실 수 있습니다. 단순 변심일 때 반품 배송비는 편도 8,000원"
         "(처음 배송비가 무료였던 경우 16,000원), 교환 배송비는 16,000원입니다. 상품 하자나 오배송은 판매자가 배송비를 부담합니다. "
         "자세한 기준은 이용약관을 확인해 주세요."),
    ],
}

# products sold on the site (checkout, admin, mail). Prices must match PRODUCTS in wrangler.jsonc.
PRODUCTS = {
    "dp-301": {"key": "dp-301", "name": "GRAZR DP-301 퍼터", "short": "DP-301 퍼터", "price": PRICE_KRW,
               "page": "/dp-301/" if SHOW_DP501 else "/", "store": STORE_URL, "note": "헤드커버 포함 · 오른손용 · 배송비 무료",
               "options": [{"key": o["key"], "label": f"{o['inch']}인치 {'블랙' if o['key'] == 'black' else '실버'}",
                            "long": f"{o['inch']}인치 · {'블랙' if o['key'] == 'black' else '실버'} 샤프트",
                            "img": f"/media/product/{o['img']}-640.webp"} for o in OPTIONS]},
    "dp-501": {"key": "dp-501", "name": "GRAZR DP-501 파크골프채", "short": "DP-501 파크골프채", "price": PRICE_501,
               "page": "/dp-501/", "store": STORE_URL_501, "note": "300개 한정 · 헤드커버 포함 · 오른손용 · 배송비 무료",
               "options": [{"key": "std", "label": "85cm 오른손용", "long": "85cm · 오른손용",
                            "img": "/media/dp501/thumb-640.webp"}]},
}
