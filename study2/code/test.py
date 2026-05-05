# -*- coding: utf-8 -*-
"""
Study 2 Streamlit 테스트: 게시물 → (생각) → 댓글 1~n 순차 노출 및 동일 크기 응답.
실행: streamlit run study2/code/test.py
"""

import html

import streamlit as st

# ----- 실험 자극 문구 (필요 시 수정) -----
POST_BODY = """
**[게시물]** (예시 텍스트)

온라인 커뮤니티에서 본 글입니다. 실제 실험에서는 연구용 게시물로 교체하세요.
"""

COMMENT_LINES = [
    "[댓글] 첫 번째 익명 댓글 내용입니다.",
    "[댓글] 두 번째 익명 댓글 내용입니다.",
    "[댓글] 세 번째 익명 댓글 내용입니다.",
    "[댓글] 네 번째 익명 댓글 내용입니다.",
]

# 모든 참여자 응답 칸 높이 통일 (픽셀)
TEXTAREA_HEIGHT = 160

_AVATAR_BOX = """
<div style="width:48px;height:48px;background:#202020;border-radius:8px;flex-shrink:0;"></div>
"""


def _init_state() -> None:
    if "s2_page" not in st.session_state:
        st.session_state.s2_page = "post"  # "post" | "comments"
    if "s2_post_thought" not in st.session_state:
        st.session_state.s2_post_thought = ""
    if "s2_comment_replies" not in st.session_state:
        st.session_state.s2_comment_replies = []  # 제출된 댓글별 응답 (순서대로)
    if "s2_n_comments_visible" not in st.session_state:
        st.session_state.s2_n_comments_visible = 0


def _css() -> None:
    st.markdown(
        """
        <style>
        .s2-post-box {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            background: #fafafa;
            margin-bottom: 1rem;
        }
        .s2-anon-row {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 0.35rem;
        }
        .s2-anon-name {
            font-weight: 600;
            font-size: 1.05rem;
            margin: 0;
            line-height: 48px;
        }
        .s2-comment-text {
            margin: 0.25rem 0 0.75rem 0;
            padding-left: 60px;
            font-size: 1rem;
            line-height: 1.5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_post() -> None:
    st.markdown('<div class="s2-post-box">', unsafe_allow_html=True)
    st.markdown(POST_BODY)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_anonymous_block(comment_text: str) -> None:
    safe = html.escape(comment_text)
    st.markdown(
        f'<div class="s2-anon-row">{_AVATAR_BOX}<p class="s2-anon-name">익명</p></div>'
        f'<div class="s2-comment-text">{safe}</div>',
        unsafe_allow_html=True,
    )


def _reply_textarea(
    label: str,
    key: str,
    *,
    value: str = "",
    disabled: bool = False,
) -> None:
    st.text_area(
        label,
        value=value,
        height=TEXTAREA_HEIGHT,
        key=key,
        disabled=disabled,
        label_visibility="collapsed",
    )


def main() -> None:
    st.set_page_config(
        page_title="Study 2 테스트 플랫폼",
        page_icon="📝",
        layout="centered",
    )
    _init_state()
    _css()

    st.title("Study 2 테스트")

    _render_post()

    if st.session_state.s2_page == "post":
        st.subheader("이 게시물에 대해 어떻게 생각하시나요?")
        thought = st.text_area(
            "게시물에 대한 생각",
            value=st.session_state.s2_post_thought,
            height=TEXTAREA_HEIGHT,
            key="s2_thought_draft",
            placeholder="여기에 생각을 적어 주세요.",
        )
        if st.button("다음", type="primary"):
            st.session_state.s2_post_thought = thought
            st.session_state.s2_page = "comments"
            st.session_state.s2_n_comments_visible = 1
            st.rerun()

    else:
        st.caption("게시물에 대한 응답을 제출하셨습니다. 아래 댓글에 차례로 답해 주세요.")

        n_vis = st.session_state.s2_n_comments_visible
        replies = st.session_state.s2_comment_replies

        for i in range(min(n_vis, len(COMMENT_LINES))):
            st.markdown("---")
            _render_anonymous_block(COMMENT_LINES[i])

            if i < len(replies):
                _reply_textarea(
                    f"댓글 {i + 1} 응답 (제출됨)",
                    key=f"s2_reply_done_{i}",
                    value=replies[i],
                    disabled=True,
                )
            elif i == len(replies):
                draft_key = f"s2_reply_active_{i}"
                if draft_key not in st.session_state:
                    st.session_state[draft_key] = ""
                st.text_area(
                    f"댓글 {i + 1}에 대한 응답",
                    height=TEXTAREA_HEIGHT,
                    key=draft_key,
                    placeholder="여기에 응답을 적어 주세요.",
                    label_visibility="collapsed",
                )
                if st.button("응답 제출", type="primary", key=f"s2_submit_{i}"):
                    text = st.session_state.get(draft_key, "")
                    st.session_state.s2_comment_replies.append(text)
                    if len(st.session_state.s2_comment_replies) < len(COMMENT_LINES):
                        st.session_state.s2_n_comments_visible += 1
                    st.rerun()
                break
            else:
                break

        if len(replies) >= len(COMMENT_LINES):
            st.success("모든 댓글 응답이 완료되었습니다. (테스트 종료)")
            if st.button("처음부터 다시"):
                st.session_state.s2_page = "post"
                st.session_state.s2_post_thought = ""
                st.session_state.s2_comment_replies = []
                st.session_state.s2_n_comments_visible = 0
                for k in list(st.session_state.keys()):
                    if str(k).startswith("s2_reply_active_") or str(k).startswith(
                        "s2_thought_draft"
                    ):
                        del st.session_state[k]
                st.rerun()


if __name__ == "__main__":
    main()
