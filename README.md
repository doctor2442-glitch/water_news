# 상하수도 뉴스 브리핑

전국 상하수도 기사와 개인하수처리시설 동향을 모아 보여 주는 정적 페이지입니다.

- `index.html`: 페이지
- `data.json`: 기사(articles), 지역 보고서(reports), 갱신 상태(meta)

## GitHub Pages 배포

1. 이 폴더의 파일을 저장소 루트에 올립니다.
2. 저장소 Settings → Pages → Source를 "Deploy from a branch", Branch를 `main` / `/ (root)`로 지정합니다.
3. 몇 분 뒤 `https://<계정>.github.io/<저장소>/`에서 열립니다.

매일 갱신은 `data.json`만 바꿔 커밋하면 페이지에 반영됩니다.
