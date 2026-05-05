# -*- coding: utf-8 -*-
"""
Study 2: 게시물 → 생각 → 고정 첫 댓글 → 참여자 응답 기반 LLM 댓글 3턴 → 설문 종료.
실행: streamlit run study2/code/test.py

환경 변수(.env) 또는 Streamlit Community Cloud → 앱 설정 → Secrets (TOML):
  API_PROVIDER = "anthropic"   # 생략 시 기본 anthropic(Claude)
  ANTHROPIC_API_KEY = "..."
  # 선택: ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
OpenAI/Gemini 사용 시 API_PROVIDER 및 해당 *_API_KEY 를 설정.
"""

from __future__ import annotations

import html
import os

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _get_env(key: str, default: str | None = None) -> str | None:
    try:
        if hasattr(st, "secrets") and st.secrets is not None and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


API_PROVIDER = (_get_env("API_PROVIDER") or "anthropic").lower()

# ----- 게시물 본문 -----
POST_BODY = """
국민취업지원제도는 저소득층이나 취업취약계층처럼 일자리를 찾는 과정에서 도움이 필요한 사람을 지원하는 공공 고용서비스다. 참여자는 고용센터나 위탁 운영기관에서 상담을 받고, 개인별 취업활동계획을 세운 뒤 직업훈련, 일경험, 구직활동 지원 등을 차례로 이용할 수 있다. 단순히 구직 등록만 하는 것이 아니라, 현재 상황을 확인하고 다음 활동을 함께 정하는 절차가 포함된다.

온라인에서는 고용24를 통해 제도 안내와 신청 절차, 구직신청, 훈련 과정, 운영기관 정보를 확인할 수 있다. 지원 내용은 참여 유형에 따라 달라지며, 일부에게는 구직촉진수당이나 취업활동비용도 지급된다. 다만 수당은 계획 수립과 실제 활동 이행 여부가 기준이 된다. 신청 전에는 소득·재산·취업경험 요건, 상담 일정, 활동 인정 기준과 제출 서류를 함께 살펴보는 것이 필요하다. 기관 안내에 따라 인정되는 활동이 다를 수 있어, 진행 중에는 상담 창구와 온라인 확인을 병행하는 편이 좋다.
""".strip()

# ----- 고정 첫 댓글 ([댓글] 말머리 없음) -----
FIRST_COMMENT_FIXED = (
    "이런 제도도 결국 본인이 움직일 의지가 있어야 의미가 있다고 봅니다. 일자리 정보, 상담, 훈련, 수당까지 지원해줘도 "
    "스스로 계획을 세우고 꾸준히 이행하지 않으면 상황은 달라지기 어렵습니다. 빈곤의 원인을 전부 사회 탓으로만 돌리기보다는, "
    "각자가 자신의 생활 태도와 구직 노력, 직업 역량을 돌아보는 계기로 삼아야 합니다. 지원은 필요하지만, 최종적으로 삶을 바꾸는 건 "
    "본인의 책임과 실행력이라고 생각합니다."
)

# LLM으로 추가되는 댓글 턴 수 (고정 첫 댓글 이후)
LLM_REPLY_TURNS = 3
# 총 댓글 개수 = 1 (고정) + 3 (LLM) = 4, 참여자 댓글 응답도 4회
TOTAL_COMMENT_BLOCKS = 1 + LLM_REPLY_TURNS

LLM_SYSTEM_PROMPT = """당신은 온라인 게시물 아래에 다는 익명 댓글 작성자 역할을 합니다.

[필수 지침]
- 빈곤·경제적 어려움의 원인을 개인의 책임에 두는 관점에서 댓글을 작성합니다. 예: 개인적 절약·가계 관리 부족, 동기·자기 노력 부족, 능력 부족, 책임감·자기규율 부족, 개인 질환·신체적 제약, 학력·역량의 미흡 등을 전제로 한 논지.
- 직전에 참여자가 작성한 응답을 읽고, 그에 맞춰 답하는 형식의 댓글을 작성합니다. 앞선 맥락이 주어지면 그 흐름을 유지합니다.
- 실제 온라인 커뮤니티 댓글처럼 자연스러운 한국어로, 2~6문장 정도로 작성합니다.
- "[댓글]" 등 말머리, 번호 매기기, "익명:" 같은 접두는 넣지 마세요. 댓글 본문만 출력합니다.
- 인용부호로 전체를 감싸지 마세요."""


def _build_llm_user_prompt(contents: list[str], replies: list[str]) -> str:
    """contents와 replies 길이는 동일(참여자가 방금 제출한 직전 응답까지 반영)."""
    lines: list[str] = [
        "다음은 연구용 게시물과, 그 아래에서 이어진 익명 댓글과 참여자 응답입니다.",
        "",
        "[게시물]",
        POST_BODY,
        "",
        "── 대화 내용 ──",
    ]
    for i in range(len(replies)):
        lines.append(f"익명 댓글 {i + 1}:")
        lines.append(contents[i])
        lines.append("")
        lines.append("참여자 응답:")
        lines.append(replies[i])
        lines.append("")
    lines.append(
        "위 맥락에서, 참여자의 **가장 마지막 응답**에 직접 대답하는 형태의 새 익명 댓글만 작성하세요. "
        "다른 설명 없이 댓글 본문만 출력합니다."
    )
    return "\n".join(lines)


def _call_llm(user_prompt: str) -> str:
    if API_PROVIDER == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=_get_env("OPENAI_API_KEY") or "")
        resp = client.chat.completions.create(
            model=_get_env("OPENAI_MODEL") or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.75,
            max_tokens=600,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text
    if API_PROVIDER == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=_get_env("ANTHROPIC_API_KEY") or "")
        resp = client.messages.create(
            model=_get_env("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514",
            max_tokens=600,
            system=LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return (resp.content[0].text or "").strip()
    if API_PROVIDER == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=_get_env("GEMINI_API_KEY") or "")
        model = genai.GenerativeModel(
            model_name=_get_env("GEMINI_MODEL") or "gemini-2.0-flash",
            system_instruction=LLM_SYSTEM_PROMPT,
        )
        resp = model.generate_content(user_prompt)
        return (resp.text or "").strip()
    return f"지원하지 않는 API_PROVIDER입니다: {API_PROVIDER}"


def _generate_next_llm_comment(contents: list[str], replies: list[str]) -> str:
    user_prompt = _build_llm_user_prompt(contents, replies)
    return _call_llm(user_prompt)


TEXTAREA_HEIGHT = 160

_AVATAR_BOX = """
<div style="width:48px;height:48px;background:#202020;border-radius:8px;flex-shrink:0;"></div>
"""


def _init_state() -> None:
    if "s2_page" not in st.session_state:
        st.session_state.s2_page = "post"
    if "s2_post_thought" not in st.session_state:
        st.session_state.s2_post_thought = ""
    if "s2_comment_contents" not in st.session_state:
        st.session_state.s2_comment_contents = [FIRST_COMMENT_FIXED]
    if "s2_comment_replies" not in st.session_state:
        st.session_state.s2_comment_replies = []
    if "s2_last_error" not in st.session_state:
        st.session_state.s2_last_error = None


def _reset_all() -> None:
    st.session_state.s2_page = "post"
    st.session_state.s2_post_thought = ""
    st.session_state.s2_comment_contents = [FIRST_COMMENT_FIXED]
    st.session_state.s2_comment_replies = []
    st.session_state.s2_last_error = None
    for k in list(st.session_state.keys()):
        if str(k).startswith("s2_reply_active_") or str(k).startswith("s2_thought_draft"):
            del st.session_state[k]


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

    if st.session_state.s2_last_error:
        st.error(st.session_state.s2_last_error)

    contents = st.session_state.s2_comment_contents
    replies = st.session_state.s2_comment_replies

    if st.session_state.s2_page == "post":
        st.subheader("이 게시물에 대해 어떻게 생각하시나요?")
        st.text_area(
            "게시물에 대한 생각",
            height=TEXTAREA_HEIGHT,
            key="s2_thought_draft",
            placeholder="여기에 생각을 적어 주세요.",
            label_visibility="collapsed",
        )
        if st.button("다음", type="primary"):
            st.session_state.s2_post_thought = st.session_state.get("s2_thought_draft", "")
            st.session_state.s2_page = "comments"
            st.session_state.s2_last_error = None
            st.rerun()

    else:
        st.caption(
            "게시물에 대한 응답을 제출하셨습니다. 아래 댓글에 차례로 답해 주세요. "
            f"(익명 댓글 {TOTAL_COMMENT_BLOCKS}개에 각각 응답하시면 설문이 종료됩니다.)"
        )

        n_blocks = len(contents)

        for i in range(n_blocks):
            st.markdown("---")
            _render_anonymous_block(contents[i])

            if i < len(replies):
                st.text_area(
                    f"댓글 {i + 1} 응답 (제출됨)",
                    value=replies[i],
                    height=TEXTAREA_HEIGHT,
                    key=f"s2_reply_done_{i}",
                    disabled=True,
                    label_visibility="collapsed",
                )
            elif i == len(replies):
                draft_key = f"s2_reply_active_{i}"
                st.text_area(
                    f"댓글 {i + 1}에 대한 응답",
                    height=TEXTAREA_HEIGHT,
                    key=draft_key,
                    placeholder="여기에 응답을 적어 주세요.",
                    label_visibility="collapsed",
                )
                if st.button("응답 제출", type="primary", key=f"s2_submit_{i}"):
                    text = (st.session_state.get(draft_key) or "").strip()
                    st.session_state.s2_comment_replies.append(text)
                    st.session_state.s2_last_error = None

                    n_rep = len(st.session_state.s2_comment_replies)
                    # 4번째 응답까지 완료 시 LLM 추가 없이 종료
                    if n_rep >= TOTAL_COMMENT_BLOCKS:
                        st.rerun()
                        break

                    # 아직 LLM 댓글 3개가 모두 나오지 않았으면 다음 댓글 생성
                    if n_rep < TOTAL_COMMENT_BLOCKS:
                        try:
                            with st.spinner("익명 댓글을 생성하는 중입니다…"):
                                next_c = _generate_next_llm_comment(
                                    st.session_state.s2_comment_contents,
                                    st.session_state.s2_comment_replies,
                                )
                            if not next_c or next_c.startswith("지원하지 않는"):
                                st.session_state.s2_last_error = (
                                    next_c or "댓글 생성 결과가 비어 있습니다. API 설정을 확인해 주세요."
                                )
                                st.session_state.s2_comment_replies.pop()
                            else:
                                st.session_state.s2_comment_contents.append(next_c)
                        except Exception as e:
                            st.session_state.s2_last_error = f"LLM 호출 오류: {e}"
                            st.session_state.s2_comment_replies.pop()
                        st.rerun()
                break
            else:
                break

        if len(replies) >= TOTAL_COMMENT_BLOCKS:
            st.success("모든 응답이 완료되어 설문을 종료합니다. 참여해 주셔서 감사합니다.")
            if st.button("처음부터 다시"):
                _reset_all()
                st.rerun()


if __name__ == "__main__":
    main()
