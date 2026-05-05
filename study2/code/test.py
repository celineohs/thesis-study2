# -*- coding: utf-8 -*-
"""
Study 2: 화면은 '게시물 + 익명 댓글 스레드', 내부는 **턴제 채팅**(익명 쪽 메시지 ↔ 참여자 메시지).

불변식(스레드 진행 중):
  len(anon_turns) == len(user_turns) + 1
종료:
  len(user_turns) == TOTAL_THREAD_USER_TURNS (= 고정 1 + LLM 3)

실행: streamlit run study2/code/test.py

Secrets: API_PROVIDER, ANTHROPIC_API_KEY 등 (기존과 동일)
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

# --- 세션 키 (기존 배포와 호환: 이름 유지) ---
S_PAGE = "s2_page"
S_POST_THOUGHT = "s2_post_thought"
S_ANON = "s2_comment_contents"  # 익명 쪽 턴 메시지 (고정 첫 줄 + LLM)
S_USER = "s2_comment_replies"  # 참여자 턴 메시지
S_ERR = "s2_last_error"

# --- 상수 ---
FIRST_ANON_TEXT = (
    "이런 제도도 결국 본인이 움직일 의지가 있어야 의미가 있다고 봅니다. 일자리 정보, 상담, 훈련, 수당까지 지원해줘도 "
    "스스로 계획을 세우고 꾸준히 이행하지 않으면 상황은 달라지기 어렵습니다. 빈곤의 원인을 전부 사회 탓으로만 돌리기보다는, "
    "각자가 자신의 생활 태도와 구직 노력, 직업 역량을 돌아보는 계기로 삼아야 합니다. 지원은 필요하지만, 최종적으로 삶을 바꾸는 건 "
    "본인의 책임과 실행력이라고 생각합니다."
)

LLM_TURNS_AFTER_FIRST = 3
# 참여자가 스레드에서 보내야 하는 메시지 수 (= 익명 말풍선 개수)
TOTAL_THREAD_USER_TURNS = 1 + LLM_TURNS_AFTER_FIRST

POST_BODY = """
국민취업지원제도는 저소득층이나 취업취약계층처럼 일자리를 찾는 과정에서 도움이 필요한 사람을 지원하는 공공 고용서비스다. 참여자는 고용센터나 위탁 운영기관에서 상담을 받고, 개인별 취업활동계획을 세운 뒤 직업훈련, 일경험, 구직활동 지원 등을 차례로 이용할 수 있다. 단순히 구직 등록만 하는 것이 아니라, 현재 상황을 확인하고 다음 활동을 함께 정하는 절차가 포함된다.

온라인에서는 고용24를 통해 제도 안내와 신청 절차, 구직신청, 훈련 과정, 운영기관 정보를 확인할 수 있다. 지원 내용은 참여 유형에 따라 달라지며, 일부에게는 구직촉진수당이나 취업활동비용도 지급된다. 다만 수당은 계획 수립과 실제 활동 이행 여부가 기준이 된다. 신청 전에는 소득·재산·취업경험 요건, 상담 일정, 활동 인정 기준과 제출 서류를 함께 살펴보는 것이 필요하다. 기관 안내에 따라 인정되는 활동이 다를 수 있어, 진행 중에는 상담 창구와 온라인 확인을 병행하는 편이 좋다.
""".strip()

LLM_SYSTEM_PROMPT = """당신은 온라인 게시물 아래에 다는 익명 댓글 작성자 역할을 합니다.

[필수 지침]
- 빈곤·경제적 어려움의 원인을 개인의 책임에 두는 관점에서 댓글을 작성합니다. 예: 개인적 절약·가계 관리 부족, 동기·자기 노력 부족, 능력 부족, 책임감·자기규율 부족, 개인 질환·신체적 제약, 학력·역량의 미흡 등을 전제로 한 논지.
- 직전에 참여자가 작성한 응답을 읽고, 그에 맞춰 답하는 형식의 댓글을 작성합니다. 앞선 맥락이 주어지면 그 흐름을 유지합니다.
- 실제 온라인 커뮤니티 댓글처럼 자연스러운 한국어로, 2~6문장 정도로 작성합니다.
- "[댓글]" 등 말머리, 번호 매기기, "익명:" 같은 접두는 넣지 마세요. 댓글 본문만 출력합니다.
- 인용부호로 전체를 감싸지 마세요."""

TEXTAREA_HEIGHT = 160

_AVATAR_BOX = """
<div style="width:48px;height:48px;background:#202020;border-radius:8px;flex-shrink:0;"></div>
"""


# ========== 환경 / LLM (기존 유지) ==========
def _get_env(key: str, default: str | None = None) -> str | None:
    try:
        if hasattr(st, "secrets") and st.secrets is not None:
            try:
                if key in st.secrets:
                    raw = st.secrets[key]
                    if raw is not None and str(raw).strip():
                        return str(raw).strip()
            except Exception:
                pass
    except Exception:
        pass
    v = os.getenv(key)
    if v is not None and str(v).strip():
        return str(v).strip()
    return default


def _first_nonempty_env(*keys: str) -> str | None:
    for k in keys:
        v = _get_env(k)
        if v:
            return v
    return None


def _anthropic_api_key() -> str | None:
    k = _first_nonempty_env(
        "ANTHROPIC_API_KEY",
        "anthropic_api_key",
        "ANTHROPIC_KEY",
    )
    if k:
        return k
    try:
        if hasattr(st, "secrets") and st.secrets is not None:
            sec = st.secrets
            sub = sec.get("anthropic") if hasattr(sec, "get") else None
            if sub is None and "anthropic" in sec:
                sub = sec["anthropic"]
            if sub is not None:
                for inner_key in ("api_key", "ANTHROPIC_API_KEY", "apiKey"):
                    val = sub.get(inner_key) if isinstance(sub, dict) else getattr(sub, inner_key, None)
                    if val is not None and str(val).strip():
                        return str(val).strip()
    except Exception:
        pass
    return None


def _api_provider() -> str:
    return (_get_env("API_PROVIDER") or "anthropic").lower()


def _build_llm_prompt(anon_turns: list[str], user_turns: list[str]) -> str:
    """user_turns는 방금까지 제출된 참여자 메시지(직전 턴 포함). anon_turns[i] ↔ user_turns[i] 쌍."""
    lines: list[str] = [
        "다음은 연구용 게시물과, 그 아래에서 이어진 익명 댓글과 참여자 응답입니다.",
        "",
        "[게시물]",
        POST_BODY,
        "",
        "── 대화 내용 ──",
    ]
    for i in range(len(user_turns)):
        lines.append(f"익명 댓글 {i + 1}:")
        lines.append(anon_turns[i])
        lines.append("")
        lines.append("참여자 응답:")
        lines.append(user_turns[i])
        lines.append("")
    lines.append(
        "위 맥락에서, 참여자의 **가장 마지막 응답**에 직접 대답하는 형태의 새 익명 댓글만 작성하세요. "
        "다른 설명 없이 댓글 본문만 출력합니다."
    )
    return "\n".join(lines)


def _llm_output_is_error(text: str) -> bool:
    if not text or text.startswith("지원하지 않는"):
        return True
    if "API 키가 없습니다" in text or "API 키를 설정" in text:
        return True
    return False


def _call_llm(user_prompt: str) -> str:
    provider = _api_provider()
    if provider == "openai":
        from openai import OpenAI

        okey = _get_env("OPENAI_API_KEY")
        if not okey:
            return "OpenAI API 키가 없습니다. Secrets 또는 환경 변수 OPENAI_API_KEY를 설정하세요."
        client = OpenAI(api_key=okey)
        resp = client.chat.completions.create(
            model=_get_env("OPENAI_MODEL") or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.75,
            max_tokens=600,
        )
        return (resp.choices[0].message.content or "").strip()
    if provider == "anthropic":
        import anthropic

        akey = _anthropic_api_key()
        if not akey:
            return (
                "Anthropic API 키가 없습니다. Streamlit Secrets에 "
                'ANTHROPIC_API_KEY = "sk-ant-api03-..." 형태로 추가했는지 확인하세요.'
            )
        client = anthropic.Anthropic(api_key=akey, timeout=120.0)
        resp = client.messages.create(
            model=_get_env("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514",
            max_tokens=600,
            system=LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()
    if provider == "gemini":
        import google.generativeai as genai

        gkey = _get_env("GEMINI_API_KEY")
        if not gkey:
            return "Gemini API 키가 없습니다. GEMINI_API_KEY를 설정하세요."
        genai.configure(api_key=gkey)
        model = genai.GenerativeModel(
            model_name=_get_env("GEMINI_MODEL") or "gemini-2.0-flash",
            system_instruction=LLM_SYSTEM_PROMPT,
        )
        resp = model.generate_content(user_prompt)
        return (resp.text or "").strip()
    return f"지원하지 않는 API_PROVIDER입니다: {provider}"


def _fetch_next_anon_message(anon: list[str], user: list[str]) -> str:
    return _call_llm(_build_llm_prompt(anon, user))


# ========== 스레드(채팅) 불변식 ==========
def _thread_invariant_ok(anon: list[str], user: list[str]) -> bool:
    """진행 중: len(anon)==len(user)+1, 종료 직후: len(anon)==len(user)==TOTAL."""
    if len(anon) < 1:
        return False
    if len(user) > TOTAL_THREAD_USER_TURNS:
        return False
    if len(anon) > len(user) + 1:
        return False
    if len(anon) < len(user):
        return False
    return True


def _repair_thread_if_broken() -> None:
    anon: list[str] = st.session_state[S_ANON]
    user: list[str] = st.session_state[S_USER]
    if _thread_invariant_ok(anon, user):
        return
    st.session_state[S_ANON] = [FIRST_ANON_TEXT]
    st.session_state[S_USER] = []
    st.session_state[S_ERR] = None


def _thread_complete(user: list[str]) -> bool:
    return len(user) >= TOTAL_THREAD_USER_TURNS


def _need_llm_after_user_message(user_count_after: int) -> bool:
    """참여자가 한 턴 보낸 직후, 아직 LLM 익명 턴이 더 남았는지."""
    return user_count_after < TOTAL_THREAD_USER_TURNS


# ========== 세션 ==========
def _init_state() -> None:
    if S_PAGE not in st.session_state:
        st.session_state[S_PAGE] = "post"
    if S_POST_THOUGHT not in st.session_state:
        st.session_state[S_POST_THOUGHT] = ""
    if S_ANON not in st.session_state:
        st.session_state[S_ANON] = [FIRST_ANON_TEXT]
    if S_USER not in st.session_state:
        st.session_state[S_USER] = []
    if S_ERR not in st.session_state:
        st.session_state[S_ERR] = None


def _reset_all() -> None:
    st.session_state[S_PAGE] = "post"
    st.session_state[S_POST_THOUGHT] = ""
    st.session_state[S_ANON] = [FIRST_ANON_TEXT]
    st.session_state[S_USER] = []
    st.session_state[S_ERR] = None
    for k in list(st.session_state.keys()):
        ks = str(k)
        if ks.startswith("s2_reply_active_") or ks.startswith("s2_thought_draft"):
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


def _render_anon_bubble(text: str) -> None:
    safe = html.escape(text)
    st.markdown(
        f'<div class="s2-anon-row">{_AVATAR_BOX}<p class="s2-anon-name">익명</p></div>'
        f'<div class="s2-comment-text">{safe}</div>',
        unsafe_allow_html=True,
    )


def _on_submit_current_turn(draft_key: str) -> None:
    """참여자 턴 제출 → 불변식 유지하며 필요 시 LLM으로 다음 익명 턴 추가."""
    text = (st.session_state.get(draft_key) or "").strip()
    anon: list[str] = st.session_state[S_ANON]
    user: list[str] = st.session_state[S_USER]

    user.append(text)
    st.session_state[S_ERR] = None

    if _thread_complete(user):
        st.rerun()
        return

    if not _need_llm_after_user_message(len(user)):
        st.rerun()
        return

    try:
        next_anon = _fetch_next_anon_message(anon, user)
        if _llm_output_is_error(next_anon):
            st.session_state[S_ERR] = next_anon or "댓글 생성에 실패했습니다. API 설정을 확인해 주세요."
            user.pop()
        else:
            anon.append(next_anon)
    except Exception as e:
        st.session_state[S_ERR] = f"LLM 호출 오류: {e}"
        user.pop()

    st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Study 2 테스트 플랫폼",
        page_icon="📝",
        layout="centered",
    )
    _init_state()
    _repair_thread_if_broken()
    _css()

    st.title("Study 2 테스트")
    _render_post()

    if st.session_state[S_ERR]:
        st.error(st.session_state[S_ERR])

    anon: list[str] = st.session_state[S_ANON]
    user: list[str] = st.session_state[S_USER]

    if st.session_state[S_PAGE] == "post":
        st.subheader("이 게시물에 대해 어떻게 생각하시나요?")
        st.text_area(
            "게시물에 대한 생각",
            height=TEXTAREA_HEIGHT,
            key="s2_thought_draft",
            placeholder="여기에 생각을 적어 주세요.",
            label_visibility="collapsed",
        )
        if st.button("다음", type="primary"):
            st.session_state[S_POST_THOUGHT] = st.session_state.get("s2_thought_draft", "")
            st.session_state[S_PAGE] = "comments"
            st.session_state[S_ERR] = None
            st.rerun()
        return

    # --- 스레드: 익명 말풍선 i번 다음에 참여자 입력(또는 이미 제출된 내용) ---
    for i in range(len(anon)):
        st.markdown("---")
        _render_anon_bubble(anon[i])

        if i < len(user):
            st.text_area(
                f"응답 (제출됨)",
                value=user[i],
                height=TEXTAREA_HEIGHT,
                key=f"s2_reply_done_{i}",
                disabled=True,
                label_visibility="collapsed",
            )
        elif i == len(user):
            draft_key = f"s2_reply_active_{i}"
            with st.form(key=f"s2_turn_form_{i}", clear_on_submit=False):
                st.text_area(
                    "이 익명 댓글에 대한 응답",
                    height=TEXTAREA_HEIGHT,
                    key=draft_key,
                    placeholder="여기에 응답을 적어 주세요.",
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button("응답 제출", type="primary")
            if submitted:
                _on_submit_current_turn(draft_key)
            break
        else:
            break

    if _thread_complete(user):
        st.success("모든 응답이 완료되어 설문을 종료합니다. 참여해 주셔서 감사합니다.")
        if st.button("처음부터 다시"):
            _reset_all()
            st.rerun()


if __name__ == "__main__":
    main()
