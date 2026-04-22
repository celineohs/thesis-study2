# -*- coding: utf-8 -*-
"""
Study 2 — 단일 페이지 프로토타입: 게시물 A + 댓글 1~4 순차 노출 및 각 댓글 평정.

로컬 실행:
  streamlit run app.py
"""

from __future__ import annotations

import html

import streamlit as st

# ── 스티뮬러스(실험 확정 시 교체) ─────────────────────────────────────────
POST_A_TITLE = "게시물 A"
POST_A_BODY = (
    "여기에 게시물 A 본문이 들어갑니다. 예: 뉴스 요약, SNS 게시글, 또는 실험 조건별로 "
    "다르게 보여줄 텍스트를 이 변수(또는 외부 JSON/CSV)로 주입하면 됩니다."
)

COMMENTS = [
    "댓글 1 — 첫 번째 댓글 내용입니다.",
    "댓글 2 — 두 번째 댓글 내용입니다.",
    "댓글 3 — 세 번째 댓글 내용입니다.",
    "댓글 4 — 네 번째 댓글 내용입니다.",
]

LIKERT_LABELS = {
    1: "전혀 그렇지 않다",
    2: "그렇지 않다",
    3: "약간 그렇지 않다",
    4: "보통이다",
    5: "약간 그렇다",
    6: "그렇다",
    7: "매우 그렇다",
}
LIKERT_QUESTION = "이 댓글에 대해 아래 문항에 얼마나 동의하십니까?"


def _init_state() -> None:
    if "stage" not in st.session_state:
        st.session_state.stage = 1  # 1~4: 평정할 댓글 번호, 5: 완료
    if "ratings" not in st.session_state:
        st.session_state.ratings = {}


def _css() -> None:
    st.markdown(
        """
        <style>
        .post-card {
            border: 1px solid #e6e6e9;
            border-radius: 12px;
            padding: 1.1rem 1.25rem;
            background: #fafafa;
            margin-bottom: 1.25rem;
        }
        .post-title { font-size: 1.15rem; font-weight: 700; margin-bottom: 0.5rem; }
        .post-body { font-size: 1.02rem; line-height: 1.55; color: #31333F; }
        .comment-wrap {
            border: 1px solid #e6e6e9;
            border-radius: 10px;
            padding: 0.85rem 1rem;
            margin-bottom: 0.75rem;
            background: #ffffff;
        }
        .comment-meta { font-size: 0.82rem; color: #6c757d; margin-bottom: 0.35rem; }
        .comment-text { font-size: 1rem; line-height: 1.5; }
        .rating-done { font-size: 0.95rem; color: #1f77b4; margin-top: 0.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Study 2 — 게시물·댓글 평정 (테스트)",
        page_icon="📋",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    _css()
    _init_state()

    st.title("테스트 플랫폼")
    st.caption("게시물 A는 항상 표시되며, 댓글은 1→4 순서로 나타납니다. 각 단계에서 평정을 제출해야 다음 댓글이 나타납니다.")

    # 게시물 A
    safe_title = html.escape(POST_A_TITLE)
    safe_body = html.escape(POST_A_BODY)
    st.markdown(
        f"""
        <div class="post-card">
            <div class="post-title">{safe_title}</div>
            <div class="post-body">{safe_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("댓글")

    stage: int = st.session_state.stage
    ratings: dict[int, int] = st.session_state.ratings

    # 이미 제출한 댓글: 내용 + 선택한 척도만 표시
    for idx in range(1, min(stage, 5)):
        text = html.escape(COMMENTS[idx - 1])
        r = ratings.get(idx)
        label = html.escape(LIKERT_LABELS.get(r, ""))
        st.markdown(
            f"""
            <div class="comment-wrap">
                <div class="comment-meta">댓글 {idx}</div>
                <div class="comment-text">{text}</div>
                <div class="rating-done">평정: <strong>{r}</strong> — {label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if stage <= 4:
        text = html.escape(COMMENTS[stage - 1])
        st.markdown(
            f"""
            <div class="comment-wrap">
                <div class="comment-meta">댓글 {stage}</div>
                <div class="comment-text">{text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(f"**{LIKERT_QUESTION}**")
        options = [f"{k}. {LIKERT_LABELS[k]}" for k in range(1, 8)]
        choice_str = st.radio(
            "척도",
            options=options,
            horizontal=False,
            key=f"likert_choice_{stage}",
            label_visibility="collapsed",
        )
        chosen = int(choice_str.split(".", 1)[0])

        if st.button("이 평정 제출 후 다음 댓글 보기", type="primary", key=f"submit_{stage}"):
            ratings[stage] = chosen
            st.session_state.ratings = ratings
            st.session_state.stage = stage + 1
            st.rerun()

    else:
        st.success("댓글 4개에 대한 평정을 모두 제출했습니다. (테스트 페이지 종료)")
        with st.expander("저장된 응답 (디버그)", expanded=False):
            st.json({"ratings": ratings})

        if st.button("처음부터 다시 시연"):
            st.session_state.stage = 1
            st.session_state.ratings = {}
            st.rerun()


if __name__ == "__main__":
    main()
