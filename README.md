# figure-vector-redraw

AI로 생성했거나 래스터로만 있는 **과학 개념도**(예: Input → Deep-learning model → Output 파이프라인 그림)를
과학적으로 점검하고, 편집 가능한 **16:9 벡터 그림**으로 다시 그린 뒤, 완성본까지 다듬는 Claude 스킬 두 개와 보조 스크립트입니다.

Two Claude skills plus helper scripts: `figure-vector-redraw` audits a raster / AI-generated scientific concept figure and
rebuilds it as a corrected, editable 16:9 vector figure (Claude Design canvas); `style-refine/` (`figure-style-refine`)
finishes it: style unification, alignment, whitespace, repeated-glyph cleanup, background, and working with the user's
own canvas edits and comments.

![A bear redraws a blurry concept diagram as editable vector paths on a tablet](assets/figure-vector-redraw-banner.webp)

## 구성

```
SKILL.md                     figure-vector-redraw: 점검 → 글자 배치 → 에셋 반영 → 배경·카드 → 검토
scripts/
  svgo.config.cjs            트레이스 SVG용 svgo 설정 (mask id·경로 순서 유지, 4–5배 축소)
  svg_split.py               mask를 유지한 채 SVG 분할 (--pieces: svgo 전, --max-bytes: 업로드 조각)
  svg_merge.py               svgo로 줄인 조각을 다시 하나로 병합
  svg_remove_boxes.py        아이콘 등 불필요한 요소를 bbox로 제거, 남은 halo를 mask로 가림
  grid_revectorize.py        공간 전사체 같은 격자 이미지를 런-길이 사각형 SVG로 재벡터화 (+ 예시용 파생 지도)
  measure_text.py            Arial 메트릭 기준 글자 폭 측정
  ring_labels.py             원형 도식(TCA 회로 등) 주변 라벨 첫 배치
  build_preview.py           Design 캔버스 아트보드(.dc.html)를 로컬 미리보기 HTML로 변환
  render.js                  Chromium(Playwright)으로 SVG·겹친 조각·페이지 렌더링

style-refine/
  SKILL.md                   figure-style-refine: AI스러움 빼기 → 완성본 다듬기 (한국어)
  requirements.txt
  scripts/
    style_audit.py           스타일 집계(팔레트·음영·선·도형·글자)와 검토 권장 항목
    preserve_check.py        전후 비교: 글자·도식 도형·도식 색·화살촉 수 보존 확인
    swap_font.py             @font-face 넣기, 글꼴 교체 전후 글자 폭·넘침 측정
    effect_opacity.py        효과 그룹 하나의 불투명도 후보와 비교 이미지
    dc_preview.py            .dc.html + blob 지도 → 로컬 PNG 미리보기
    bump_text.py             역할별 글자 키우기 (사용자가 옮긴 기준점 유지)
    ring_label_gap.py        고리 라벨을 같은 잉크 간격(기본 16px)으로 배치
    ring_arrows.py           한 단계 = 화살표 하나, 같은 모양의 순환 화살표 고리 (꼬리를 무는 형/띄운 형)
    umap_spread.py           산점도를 군집 모양을 지키며 위아래로 펼치기
```

## 스킬 설치

- **Claude 앱**: `SKILL.md`(벡터 재작성)와 `style-refine/SKILL.md`(다듬기)를 각각 스킬로 추가합니다. 스킬 본문은 필요할 때 이 저장소의 스크립트를 내려받아 씁니다.
- **Claude Code**: 루트를 `~/.claude/skills/figure-vector-redraw/`에, `style-refine/` 폴더를 `~/.claude/skills/figure-style-refine/`에 복사합니다.
- Python 의존성: `pip install -r requirements.txt -r style-refine/requirements.txt`, 그리고 `playwright install chromium`.

## 작업 흐름 요약

1. **과학적 점검**: 중복·누락 라벨, 화살표 수와 반응 수(한 단계 = 화살표 하나), 표기법(GAT의 α_ij와 W), flux vs activity, AI 워터마크, 선행 연구.
2. **배치**: 1920×1080, 내용에 맞춘 열 폭(출력 열이 가장 넓게), 카드마다 왼쪽 축 하나, 처음부터 최종 글자 크기(열 제목 36 · 카드 제목 28 · 캡션 25 · 라벨 23 · 주석 20).
3. **에셋 반영**: 트레이스 SVG를 svgo로 축소하고, 2MB 업로드 제한에 맞게 조각내 한 요소에 겹쳐 올리기. 격자 지도는 재벡터화. 잘린 그림은 같은 구조의 벡터로 완성.
4. **배경·카드**: 기본은 옅은 단색(#f3f5f8) 바탕에 흰 카드. 원본 느낌의 장식은 한 요소로 묶어 한 번에 지울 수 있게.
5. **다듬기(style-refine)**: 스타일 토큰 정리, 효과 하나만 조절, 고리 화살표 통일, 글자 배치 정렬 패스, 여백 채우기, 사용자의 직접 수정·코멘트 반영.
6. **검토**: 로컬 미리보기로 잘림·정렬·겹침을 보고, 강도 2–3개를 나란히 그려 고르게 함. 보존 검사는 "변경 없음"이어야 함.

## 참고

- 그림 원본·에셋·데이터는 이 저장소에 포함하지 않습니다.
- `grid_revectorize.py --ramp`로 만든 파생 지도와 `umap_spread.py --move`로 옮긴 군집은 **예시용**입니다. 실제 측정값·실제 임베딩에는 쓰지 않습니다.
- 다듬기 규칙의 일부(배경 단색, 하이픈 줄바꿈 금지, 큰 제목)는 한 사용자의 결정을 정리한 것이며, 다른 그림에서는 선택지로 제시합니다.
