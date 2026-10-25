# figure-vector-redraw

AI로 생성했거나 래스터로만 있는 **과학 개념도**(예: Input → Deep-learning model → Output 파이프라인 그림)를
과학적으로 점검하고, 편집 가능한 **16:9 벡터 그림**으로 다시 그리는 Claude 스킬과 보조 스크립트입니다.

A Claude skill plus helper scripts for auditing a raster / AI-generated scientific concept figure and rebuilding
it as a corrected, editable 16:9 vector figure (Claude Design canvas), using traced SVG pieces of the original.

## 구성

```
SKILL.md                 Claude 스킬 본문 (작업 단계, 레이아웃 규칙, 노하우)
scripts/
  svgo.config.cjs        트레이스 SVG용 svgo 설정 (mask id·경로 순서 유지, 4–5배 축소)
  svg_split.py           mask를 유지한 채 SVG 분할 (--pieces: svgo 전, --max-bytes: 업로드 조각)
  svg_merge.py           svgo로 줄인 조각을 다시 하나로 병합
  svg_remove_boxes.py    아이콘 등 불필요한 요소를 bbox로 제거, 남은 halo를 mask로 가림
  grid_revectorize.py    공간 전사체 같은 격자 이미지를 런-길이 사각형 SVG로 재벡터화 (+ 예시용 파생 지도)
  measure_text.py        Arial 메트릭 기준 글자 폭 측정
  ring_labels.py         원형 도식(TCA 회로 등) 주변 라벨 위치 계산
  build_preview.py       Design 캔버스 아트보드(.dc.html)를 로컬 미리보기 HTML로 변환
  render.js              Chromium(Playwright)으로 SVG·겹친 조각·페이지 렌더링
```

## 스킬 설치

- **Claude 앱**: 이 저장소의 `SKILL.md`(필요하면 `scripts/` 포함)를 스킬로 추가합니다.
- **Claude Code**: 폴더째 `~/.claude/skills/figure-vector-redraw/`에 복사합니다.

## 작업 흐름 요약

1. **과학적 점검**: 중복·누락 라벨, 화살표 수와 반응 수, 표기법(GAT의 α_ij와 W), flux vs activity, 하이픈, AI 워터마크, 선행 연구.
2. **글자 배치**: 1920×1080, 3열 그리드, 글자 크기 3단계(제목 21 / 라벨 16 / 보조 13), 실제 글자 폭 측정 후 배치.
3. **에셋 반영**: 트레이스 SVG를 svgo로 축소하고, 2MB 업로드 제한에 맞게 조각내 한 요소에 겹쳐 올리기. 격자 지도는 재벡터화.
4. **배경·카드**: 회로기판 무늬는 여백과 카드 사이 틈에만, 열마다 카드 배치.
5. **검토**: 로컬 미리보기를 렌더링해 잘림·정렬·겹침 확인 후 수정.

## 스크립트 사용 예

```bash
# 준비
pip install pillow numpy
npm i svgo@3.3.2 playwright && npx playwright install chromium

# 큰 트레이스 SVG 축소: 조각 → svgo → 병합 → 업로드 크기로 분할
python3 scripts/svg_split.py raw.svg work/raw --pieces 6
for f in work/raw_part*.svg; do npx svgo --config scripts/svgo.config.cjs -i "$f" -o "${f%.svg}.min.svg"; done
python3 scripts/svg_merge.py merged.svg work/raw_part*.min.svg
python3 scripts/svg_split.py merged.svg upload/art --max-bytes 1500000
node scripts/render.js stack check.png --width 494 --height 251 upload/art_part*.svg

# 아이콘 제거 (원본 트레이스 좌표계, scale(0.5) 안이면 2배 좌표)
python3 scripts/svg_remove_boxes.py gat.svg gat_clean.svg --box 170,72,250,146 --mask-ellipse 210,112,46,33

# 공간 지도 재벡터화 (2배 렌더 PNG에서)
node scripts/render.js svg spatial.svg spatial@2x.png --width 224 --height 239 --scale 2
python3 scripts/grid_revectorize.py spatial@2x.png st_input.svg --cell 2 --fix 199,104,215,117

# 라벨 배치
python3 scripts/ring_labels.py --center 1580,646 --radius 174 --size 16 \
    --label "Citrate:-90.5" --label "α-Ketoglutarate:34" --bounds 1320,1840

# 아트보드 미리보기
python3 scripts/build_preview.py Artboard.dc.html preview.html --blob-map blobs.json --hole titleTerm="Activity Inference"
node scripts/render.js page preview.html preview.png --scale 2
```

## 참고

- 그림 원본·에셋·데이터는 이 저장소에 포함하지 않습니다.
- `grid_revectorize.py --ramp`로 만든 파생 지도는 **예시용**입니다. 그림에 실제 측정값이 아니라고 표시하세요.
