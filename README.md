# thesis-study2

Study 2 Streamlit 테스트: **[게시물] → 생각 응답 → [익명/검은 프로필] + [댓글] 순차 노출**, 고정 첫 댓글 + **Claude(Anthropic) 댓글 3턴**.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
# 또는
streamlit run study2/code/test.py
```

로컬에서는 프로젝트 루트에 `.env` 파일을 두고 사용할 수 있습니다.

## Streamlit Community Cloud (Secrets)

배포 후 앱 → **Settings → Secrets**에 아래 형식으로 저장합니다 (기본 모델은 **Anthropic Claude**).

```toml
API_PROVIDER = "anthropic"
ANTHROPIC_API_KEY = "your-api-key"
# 선택
# ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
```

`API_PROVIDER`를 생략하면 코드 기본값은 `anthropic`입니다. OpenAI 등 다른 제공자를 쓰려면 `API_PROVIDER`와 해당 `*_API_KEY`를 맞춰 주세요.

## Streamlit Community Cloud (연결)

1. [Streamlit Cloud](https://share.streamlit.io/)에서 GitHub 저장소 `celineohs/thesis-study2` 연결
2. Main file path: `app.py` (내부에서 `study2/code/test.py` 실행)
3. Branch: `main`

저장소: https://github.com/celineohs/thesis-study2
