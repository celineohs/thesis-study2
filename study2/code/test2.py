# -*- coding: utf-8 -*-
"""
Study 2 — Streamlit 옵션 2 프로토타입: 게시물 제시 + 응답 입력란에 AI 이어쓰기 제안.

Streamlit 특성상 브라우저 타이핑마다 즉시 호출하는 UX는 제한적이라,
(1) 첫 진입 시 1회 자동 제안, (2) 버튼으로 추가 제안 — 두 가지를 제공합니다.

Secrets / 환경변수: API_PROVIDER(anthropic|openai|gemini), 해당 API 키, 선택 모델명.

실행: streamlit run study2/code/test2.py
"""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# --- 게시물·프롬프트 (실험에 맞게 수정) ---
POST_BODY = """
국민취업지원제도는 저소득층이나 취업취약계층처럼 일자리를 찾는 과정에서 도움이 필요한 사람을 지원하는 공공 고용서비스다.
온라인에서는 고용24를 통해 제도 안내와 신청 절차를 확인할 수 있다.
""".strip()

SUGGESTION_SYSTEM = """당신은 연구용 글쓰기 보조 도구입니다.
사용자가 게시물에 대해 응답란에 쓴 글에 이어 붙일 수 있는 **짧은 한국어 제안**(1~3문장)만 출력합니다.
출력에는 말머리, 따옴표로 전체 감싸기, 번호를 넣지 않습니다."""

S2_DRAFT = "s2_test2_draft"
S2_LAST_SUGG = "s2_test2_last_suggestion"
S2_FIRST_AUTO_DONE = "s2_test2_first_autocomplete_done"
S2_N_SUGG_REQUESTED = "s2_test2_n_suggestions_requested"
S2_N_SUGG_ACCEPTED = "s2_test2_n_suggestions_accepted"
S2_ERR = "s2_test2_err"


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
    k = _first_nonempty_env("ANTHROPIC_API_KEY", "anthropic_api_key", "ANTHROPIC_KEY")
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


def _build_user_prompt_for_suggestion(draft_so_far: str) -> str:
    draft = (draft_so_far or "").strip()
    return "\n".join(
        [
            "[게시물]",
            POST_BODY,
            "",
            "[사용자가 응답란에 지금까지 쓴 글 (없을 수 있음)]",
            draft if draft else "(비어 있음)",
            "",
            "위에 이어질 짧은 제안만 출력하세요.",
        ]
    )


def _llm_output_is_error(text: str) -> bool:
    if not text or text.startswith("지원하지 않는"):
        return True
    if "API 키가 없습니다" in text or "API 키를 설정" in text:
        return True
    return False


def _call_llm(
    user_prompt: str,
    *,
    system: str,
    max_tokens: int = 320,
    temperature: float = 0.65,
) -> str:
    provider = _api_provider()
    if provider == "openai":
        from openai import OpenAI

        okey = _get_env("OPENAI_API_KEY")
        if not okey:
            return "OpenAI API 키가 없습니다. OPENAI_API_KEY를 설정하세요."
        client = OpenAI(api_key=okey)
        resp = client.chat.completions.create(
            model=_get_env("OPENAI_MODEL") or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    if provider == "anthropic":
        import anthropic

        akey = _anthropic_api_key()
        if not akey:
            return "Anthropic API 키가 없습니다. ANTHROPIC_API_KEY(Streamlit Secrets)를 설정하세요."
        client = anthropic.Anthropic(api_key=akey, timeout=120.0)
        resp = client.messages.create(
            model=_get_env("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system,
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
            system_instruction=system,
        )
        resp = model.generate_content(
            user_prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return (resp.text or "").strip()
    return f"지원하지 않는 API_PROVIDER입니다: {provider}"


def _merge_suggestion_into_draft(suggestion: str) -> None:
    sug = (suggestion or "").strip()
    if not sug:
        return
    cur = (st.session_state.get(S2_DRAFT) or "").rstrip()
    st.session_state[S2_DRAFT] = (cur + " " + sug).strip() if cur else sug


def _init_session() -> None:
    if S2_LAST_SUGG not in st.session_state:
        st.session_state[S2_LAST_SUGG] = ""
    if S2_FIRST_AUTO_DONE not in st.session_state:
        st.session_state[S2_FIRST_AUTO_DONE] = False
    if S2_N_SUGG_REQUESTED not in st.session_state:
        st.session_state[S2_N_SUGG_REQUESTED] = 0
    if S2_N_SUGG_ACCEPTED not in st.session_state:
        st.session_state[S2_N_SUGG_ACCEPTED] = 0
    if S2_ERR not in st.session_state:
        st.session_state[S2_ERR] = None
    if S2_DRAFT not in st.session_state:
        st.session_state[S2_DRAFT] = ""


def _request_suggestion() -> str | None:
    """LLM 호출 후 마지막 제안 문자열을 반환. 실패 시 None, S2_ERR 설정."""
    st.session_state[S2_N_SUGG_REQUESTED] = int(st.session_state[S2_N_SUGG_REQUESTED]) + 1
    draft = (st.session_state.get(S2_DRAFT) or "").strip()
    try:
        prompt = _build_user_prompt_for_suggestion(draft)
        out = _call_llm(prompt, system=SUGGESTION_SYSTEM)
    except Exception as e:
        st.session_state[S2_ERR] = f"LLM 오류: {e}"
        return None
    if _llm_output_is_error(out):
        st.session_state[S2_ERR] = out or "제안 생성에 실패했습니다."
        return None
    st.session_state[S2_ERR] = None
    st.session_state[S2_LAST_SUGG] = out.strip()
    return st.session_state[S2_LAST_SUGG]


def _maybe_first_autocomplete(auto_on_load: bool) -> None:
    """페이지당 최대 1회: auto_on_load가 켜져 있을 때만 첫 제안을 붙입니다."""
    if st.session_state[S2_FIRST_AUTO_DONE]:
        return
    if not auto_on_load:
        return
    st.session_state[S2_FIRST_AUTO_DONE] = True
    with st.spinner("첫 입력 제안을 불러오는 중…"):
        sugg = _request_suggestion()
    if sugg:
        _merge_suggestion_into_draft(sugg)


def _export_payload() -> dict:
    return {
        "study": "study2",
        "script": "test2.py",
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "post": POST_BODY,
        "response_draft": st.session_state.get(S2_DRAFT) or "",
        "last_suggestion": st.session_state.get(S2_LAST_SUGG) or "",
        "n_suggestions_requested": int(st.session_state.get(S2_N_SUGG_REQUESTED) or 0),
        "n_suggestions_accepted": int(st.session_state.get(S2_N_SUGG_ACCEPTED) or 0),
        "api_provider": _api_provider(),
    }


def _css() -> None:
    st.markdown(
        """
        <style>
        .t2-title { font-size: 1.85rem; font-weight: 700; margin: 0 0 0.5rem 0; }
        .t2-post {
            border: 1px solid #e6e6e6;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            background: #fafafa;
            white-space: pre-wrap;
            margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Study 2 — 응답 + AI 제안", layout="centered")
    _init_session()
    _css()

    st.sidebar.markdown("**API**")
    st.sidebar.caption(f"provider: `{_api_provider()}`")
    auto_on_load = st.sidebar.toggle("페이지 로드 시 첫 제안 자동 생성", value=True)
    if st.sidebar.button("세션 초기화"):
        for k in (
            S2_DRAFT,
            S2_LAST_SUGG,
            S2_FIRST_AUTO_DONE,
            S2_N_SUGG_REQUESTED,
            S2_N_SUGG_ACCEPTED,
            S2_ERR,
        ):
            st.session_state.pop(k, None)
        _init_session()
        st.rerun()

    st.markdown('<p class="t2-title">게시물</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="t2-post">{html.escape(POST_BODY)}</div>', unsafe_allow_html=True)

    st.subheader("응답")
    _maybe_first_autocomplete(auto_on_load)

    st.text_area(
        "응답 입력",
        height=200,
        key=S2_DRAFT,
        placeholder="여기에 응답을 작성하세요. 자동 제안이 붙었을 수 있습니다.",
        label_visibility="collapsed",
    )

    if st.session_state[S2_ERR]:
        st.error(st.session_state[S2_ERR])

    c1, c2, c3 = st.columns(3)
    with c1:
        gen = st.button("AI 제안 생성", type="secondary")
    with c2:
        accept = st.button("마지막 제안을 끝에 붙이기", type="primary")
    with c3:
        save_json = st.button("로컬 JSON 저장")

    if gen:
        with st.spinner("제안 생성 중…"):
            _request_suggestion()
        st.rerun()

    if accept:
        s = (st.session_state.get(S2_LAST_SUGG) or "").strip()
        if not s:
            st.warning("먼저 「AI 제안 생성」으로 제안을 만드세요.")
        else:
            _merge_suggestion_into_draft(s)
            st.session_state[S2_N_SUGG_ACCEPTED] = int(st.session_state[S2_N_SUGG_ACCEPTED]) + 1
            st.rerun()

    if st.session_state.get(S2_LAST_SUGG):
        with st.expander("마지막 생성 제안 (미리보기)", expanded=False):
            st.write(st.session_state[S2_LAST_SUGG])

    if save_json:
        os.makedirs("conversations", exist_ok=True)
        path = os.path.join(
            "conversations",
            f"study2_test2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_export_payload(), f, ensure_ascii=False, indent=2)
        st.success(f"저장됨: `{path}`")

    st.caption(
        "요청 수·수락 수는 `n_suggestions_requested` / `n_suggestions_accepted`로 기록됩니다. "
        "실험 조건(system 프롬프트)은 코드 상단 `SUGGESTION_SYSTEM`에서 바꾸면 됩니다."
    )


if __name__ == "__main__":
    main()
