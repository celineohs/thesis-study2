# thesis-study2

Study 2 Streamlit: **게시물** → 참가자의 **생각** → 첫 **익명** 댓글 + **AI(LLM) 익명** 댓글을 연속으로 보여 준 뒤, 참가자는 **AI 댓글에 1회만** 응답하고 종료합니다.

[AI 제안]은 AI 댓글 본문의 첫 단어를 회색으로 표시합니다. 회색 단축키 안내 영역을 클릭한 뒤 **F2** 키, 또는 **「첫 단어 넣기」** 버튼으로 응답 입력란에 넣을 수 있습니다.

동일 코드는 모노레포 **[2026prejudice](https://github.com/celineohs/2026prejudice)** 에서도 관리됩니다.

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
