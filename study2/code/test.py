# -*- coding: utf-8 -*-
"""
Study 2: 게시물 + 익명 댓글 UI. 첫 익명 1 + AI(LLM) 익명 1을 연속으로 보여 준 뒤,
참여자는 **AI 댓글에 대해 1회만** 응답하고 종료합니다.

불변식: len(anon_turns) in {1, 2}, len(user_turns) <= 1, 완료 시 len(anon_turns)==2 and len(user_turns)==1
종료: 마지막 제출 후 JSON 저장 + Study1과 동일한 Google Drive 업로드

게시물에 대한 생각·AI 댓글 응답 입력란: 페이지에 들어오면 Claude 등 LLM이 **한 번** 자동으로 이어 쓸 제안을 생성해 입력란에 붙입니다(별도 버튼 없음).

자동완성 시스템 프롬프트: 개인적 책임 관점의 빈곤 서술에 기반한 제안.

Secrets: API_PROVIDER, ANTHROPIC_API_KEY, Study1과 동일 Drive 키(GOOGLE_DRIVE_FOLDER_ID 등)

실행: streamlit run study2/code/test.py
"""

from __future__ import annotations

import html
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 같은 폴더의 gdrive_upload.py (Streamlit Cloud 배포 시 study2/code 전체 동봉)
_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
if _CODE_DIR not in sys.path:
    sys.path.insert(0, _CODE_DIR)
from gdrive_upload import upload_file_to_drive  # noqa: E402

# --- 세션 키 ---
S_PAGE = "s2_page"
S_POST_THOUGHT = "s2_post_thought"
S_ANON = "s2_comment_contents"
S_USER = "s2_comment_replies"
S_ERR = "s2_last_error"
S_SAVED = "s2_conversation_saved"
S_GDRIVE_RESULT = "s2_gdrive_upload_result"
S_AUTOCOMPLETE = "s2_reply_autocomplete_suggestion"
S_POST_AUTOCOMPLETE = "s2_post_thought_autocomplete_suggestion"

SAVE_PREFIX = "study2-thread"
S2_REPLY_DRAFT_KEY = "s2_reply_final_draft"
S2_POST_AUTOFILL_DONE = "s2_post_autofill_done"
S2_REPLY_AUTOFILL_DONE = "s2_reply_autofill_done"

# --- 상수: AI(LLM) 댓글 1개 본 뒤 참여자 1회 응답 ---
FIRST_ANON_TEXT = (
    "이런 제도도 결국 본인이 움직일 의지가 있어야 의미가 있다고 봅니다. 일자리 정보, 상담, 훈련, 수당까지 지원해줘도 "
    "스스로 계획을 세우고 꾸준히 이행하지 않으면 상황은 달라지기 어렵습니다. 빈곤의 원인을 전부 사회 탓으로만 돌리기보다는, "
    "각자가 자신의 생활 태도와 구직 노력, 직업 역량을 돌아보는 계기로 삼아야 합니다. 지원은 필요하지만, 최종적으로 삶을 바꾸는 건 "
    "본인의 책임과 실행력이라고 생각합니다."
)

TOTAL_THREAD_USER_TURNS = 1

# 다음 익명 댓글 표시 전 지연: 사람이 비슷한 길이를 쓰는 시간을 가정 (글자수 기반 + 상한)
TYPING_DELAY_BASE_SEC = 2.8
TYPING_DELAY_PER_CHAR_SEC = 0.11
TYPING_DELAY_MAX_SEC = 38.0

POST_BODY = """
국민취업지원제도는 저소득층이나 취업취약계층처럼 일자리를 찾는 과정에서 도움이 필요한 사람을 지원하는 공공 고용서비스다. 참여자는 고용센터나 위탁 운영기관에서 상담을 받고, 개인별 취업활동계획을 세운 뒤 직업훈련, 일경험, 구직활동 지원 등을 차례로 이용할 수 있다. 단순히 구직 등록만 하는 것이 아니라, 현재 상황을 확인하고 다음 활동을 함께 정하는 절차가 포함된다.

온라인에서는 고용24를 통해 제도 안내와 신청 절차, 구직신청, 훈련 과정, 운영기관 정보를 확인할 수 있다. 지원 내용은 참여 유형에 따라 달라지며, 일부에게는 구직촉진수당이나 취업활동비용도 지급된다. 다만 수당은 계획 수립과 실제 활동 이행 여부가 기준이 된다. 신청 전에는 소득·재산·취업경험 요건, 상담 일정, 활동 인정 기준과 제출 서류를 함께 살펴보는 것이 필요하다. 기관 안내에 따라 인정되는 활동이 다를 수 있어, 진행 중에는 상담 창구와 온라인 확인을 병행하는 편이 좋다.
""".strip()

LLM_SYSTEM_PROMPT = """당신은 온라인 게시물 아래에 다는 익명 댓글 작성자 역할을 합니다.

[필수 지침]
- 빈곤·경제적 어려움의 원인을 개인의 책임에 두는 관점에서 댓글을 작성합니다. 예: 개인적 절약·가계 관리 부족, 동기·자기 노력 부족, 능력 부족, 책임감·자기규율 부족, 개인 질환·신체적 제약, 학력·역량의 미흡 등을 전제로 한 논지.
- 직전 맥락(다른 익명 댓글, 필요 시 참여자가 게시물에 대해 적은 생각)을 읽고 그에 맞춰 이어지는 댓글을 작성합니다. 참여자가 아직 스레드에 글을 남기지 않은 경우라면, 첫 익명 댓글·게시물·참여자의 생각에 맞춰 자연스럽게 동조하거나 반박합니다.
- 실제 온라인 커뮤니티 댓글처럼 자연스러운 한국어로, 2~6문장 정도로 작성합니다.
- "[댓글]" 등 말머리, 번호 매기기, "익명:" 같은 접두는 넣지 마세요. 댓글 본문만 출력합니다.
- 인용부호로 전체를 감싸지 마세요."""

AUTOCOMPLETE_SYSTEM_PROMPT = """당신은 효과적인 AI 지원 도구입니다. 빈곤은 개인적 책임 때문이라는 주장에 기반한 제안들을 제공하세요.

[역할]
- 참여자가 이미 입력한 글(있을 수 있음)에 이어 붙일 수 있는 **짧은 한국어 제안**을 합니다. 1~3문장 또는 자연스러운 한 구절 정도로, 너무 길지 않게 합니다.
- 말투는 실제 댓글·게시물 반응처럼 자연스럽게 하되, 참여자 본인의 의견에 가깝게 씁니다.
- 맥락(게시물, 익명 댓글 등 사용자 메시지에 주어진 내용)에 맞게 이어집니다. 제안 내용은 위 지침(개인적 책임 관점)과 일관되게 합니다.

[출력 규칙]
- 제안 문장만 출력합니다. 말머리, 따옴표로 전체 감싸기, 번호, "제안:" 같은 접두는 넣지 않습니다."""

TEXTAREA_HEIGHT = 160

_AVATAR_BOX = """
<div style="width:48px;height:48px;background:#202020;border-radius:8px;flex-shrink:0;"></div>
"""


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


def _query_param_first(name: str) -> str | None:
    try:
        qp = st.query_params
        if name not in qp:
            return None
        v = qp[name]
        if isinstance(v, list):
            return str(v[0]).strip() if v else None
        return str(v).strip() if v else None
    except Exception:
        return None


def _participant_id() -> str:
    if st.session_state.get("s2_participant_id"):
        return st.session_state.s2_participant_id
    for key in ("participant", "pid", "PROLIFIC_PID", "subject"):
        qv = _query_param_first(key)
        if qv:
            st.session_state.s2_participant_id = qv
            return qv
    st.session_state.s2_participant_id = f"s2_{uuid.uuid4().hex[:12]}"
    return st.session_state.s2_participant_id


def _build_llm_second_anon_prompt(first_anon: str, post_thought: str) -> str:
    """참여자 스레드 응답 전: 첫 익명 댓글·게시물·(선택) 게시물에 대한 생각만으로 차기 익명 댓글 생성."""
    lines: list[str] = [
        "다음은 연구용 게시물, 참여자가 게시물에 대해 먼저 작성한 생각(있을 수 있음), 그리고 게시물 아래 첫 익명 댓글입니다.",
        "",
        "[게시물]",
        POST_BODY,
        "",
    ]
    thought = (post_thought or "").strip()
    if thought:
        lines.extend(["[참여자가 게시물에 대해 작성한 생각]", thought, ""])
    lines.extend(
        [
            "── 첫 익명 댓글 ──",
            first_anon,
            "",
            "참여자는 아직 이 스레드(댓글 달기)에는 글을 남기지 않았습니다.",
            "위 맥락에서, 첫 익명 댓글에 이어지는 **또 다른 익명 작성자의 차기 댓글**만 작성하세요. "
            "게시물과 첫 댓글의 논지, 그리고 참여자가 게시물에 대해 적은 생각이 있다면 그것도 참고해 자연스럽게 이어가면 됩니다.",
            "다른 설명 없이 댓글 본문만 출력합니다.",
        ]
    )
    return "\n".join(lines)


def _build_reply_autocomplete_prompt(
    first_anon: str,
    ai_comment: str,
    draft_so_far: str,
    post_thought: str,
) -> str:
    """AI 익명 댓글에 답하는 참여자 응답용 LLM 자동완성."""
    lines: list[str] = [
        "다음은 연구용 게시물, 게시물 아래 익명 댓글, 마지막 AI 익명 댓글, 참여자가 응답 칸에 지금까지 쓴 글입니다.",
        "",
        "[게시물]",
        POST_BODY,
        "",
    ]
    thought = (post_thought or "").strip()
    if thought:
        lines.extend(["[참여자가 게시물에 대해 먼저 적은 생각]", thought, ""])
    lines.extend(
        [
            "[첫 익명 댓글]",
            first_anon,
            "",
            "[마지막 AI 익명 댓글 — 참여자가 이에 답하는 중]",
            ai_comment,
            "",
            "[참여자가 지금까지 응답 칸에 적은 글 (비어 있을 수 있음)]",
            (draft_so_far.strip() if (draft_so_far or "").strip() else "(비어 있음)"),
            "",
            "위 맥락에서 참여자 응답을 이어서 쓸 **짧은 제안**만 출력하세요.",
        ]
    )
    return "\n".join(lines)


def _build_post_thought_autocomplete_prompt(draft_so_far: str) -> str:
    """게시물에 대한 생각 입력란용 LLM 자동완성."""
    lines: list[str] = [
        "다음은 연구용 게시물과, 참여자가 게시물에 대해 지금까지 입력한 글입니다.",
        "",
        "[게시물]",
        POST_BODY,
        "",
        "[참여자가 지금까지 입력한 글 (비어 있을 수 있음)]",
        (draft_so_far.strip() if (draft_so_far or "").strip() else "(비어 있음)"),
        "",
        "위 맥락에서 게시물에 대한 생각을 이어서 쓸 **짧은 제안**만 출력하세요.",
    ]
    return "\n".join(lines)


def _llm_output_is_error(text: str) -> bool:
    if not text or text.startswith("지원하지 않는"):
        return True
    if "API 키가 없습니다" in text or "API 키를 설정" in text:
        return True
    return False


def _call_llm(
    user_prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 600,
    temperature: float = 0.75,
) -> str:
    sys_text = LLM_SYSTEM_PROMPT if system is None else system
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
                {"role": "system", "content": sys_text},
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
            return (
                "Anthropic API 키가 없습니다. Streamlit Secrets에 "
                'ANTHROPIC_API_KEY = "sk-ant-api03-..." 형태로 추가했는지 확인하세요.'
            )
        client = anthropic.Anthropic(api_key=akey, timeout=120.0)
        resp = client.messages.create(
            model=_get_env("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=sys_text,
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
            system_instruction=sys_text,
        )
        resp = model.generate_content(
            user_prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return (resp.text or "").strip()
    return f"지원하지 않는 API_PROVIDER입니다: {provider}"


def _human_like_delay_before_show_comment(reply_text: str) -> None:
    """LLM 결과를 받은 뒤, 사람이 비슷한 분량을 작성하는 것처럼 보이도록 표시 전만 지연."""
    n = len(reply_text or "")
    delay = TYPING_DELAY_BASE_SEC + n * TYPING_DELAY_PER_CHAR_SEC
    delay = min(delay, TYPING_DELAY_MAX_SEC)
    delay += random.uniform(-0.5, 0.8)
    delay = max(1.8, delay)
    placeholder = st.empty()
    deadline = time.monotonic() + delay
    while True:
        remain = deadline - time.monotonic()
        if remain <= 0:
            break
        placeholder.caption(f"다음 익명 댓글이 표시됩니다… (약 {max(1, int(remain + 0.99))}초)")
        time.sleep(min(1.0, remain))
    placeholder.empty()


def _messages_for_export(anon: list[str], user: list[str]) -> list[dict]:
    """첫·AI 익명은 연속 assistant, 마지막에 참여자 1회 user."""
    out: list[dict] = []
    for a in anon:
        out.append({"role": "assistant", "content": a})
    for u in user:
        out.append({"role": "user", "content": u})
    return out


def _save_conversation_to_disk_and_drive() -> str | None:
    """마지막 참여자 제출 직후 1회: 로컬 JSON + Google Drive (Study1과 동일 upload_file_to_drive)."""
    if st.session_state.get(S_SAVED):
        return None
    os.makedirs("conversations", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = _participant_id()
    path = f"conversations/{SAVE_PREFIX}_{pid}_{ts}.json"
    anon = list(st.session_state[S_ANON])
    user = list(st.session_state[S_USER])
    data = {
        "study": "study2",
        "save_prefix": SAVE_PREFIX,
        "participant_id": pid,
        "saved_at": ts,
        "post_thought": st.session_state.get(S_POST_THOUGHT) or "",
        "anon_turns": anon,
        "user_turns": user,
        "messages": _messages_for_export(anon, user),
        "total_user_turns": TOTAL_THREAD_USER_TURNS,
        "llm_reply_autocomplete_last": (st.session_state.get(S_AUTOCOMPLETE) or "").strip(),
        "llm_post_thought_autocomplete_last": (st.session_state.get(S_POST_AUTOCOMPLETE) or "").strip(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    ok, msg = upload_file_to_drive(path, _get_env)
    st.session_state[S_GDRIVE_RESULT] = (ok, msg)
    return path


# ========== 스레드 불변식 ==========
def _thread_invariant_ok(anon: list[str], user: list[str]) -> bool:
    if len(anon) not in (1, 2) or len(user) > 1:
        return False
    if len(anon) == 1:
        return len(user) == 0
    return len(user) <= 1


def _repair_thread_if_broken() -> None:
    anon: list[str] = st.session_state[S_ANON]
    user: list[str] = st.session_state[S_USER]
    if _thread_invariant_ok(anon, user):
        return
    st.session_state[S_ANON] = [FIRST_ANON_TEXT]
    st.session_state[S_USER] = []
    st.session_state[S_ERR] = None
    st.session_state[S_AUTOCOMPLETE] = ""


def _thread_complete(anon: list[str], user: list[str]) -> bool:
    return len(anon) == 2 and len(user) >= TOTAL_THREAD_USER_TURNS


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
    if S_SAVED not in st.session_state:
        st.session_state[S_SAVED] = False
    if S_AUTOCOMPLETE not in st.session_state:
        st.session_state[S_AUTOCOMPLETE] = ""
    if S_POST_AUTOCOMPLETE not in st.session_state:
        st.session_state[S_POST_AUTOCOMPLETE] = ""


def _reset_all() -> None:
    st.session_state[S_PAGE] = "post"
    st.session_state[S_POST_THOUGHT] = ""
    st.session_state[S_ANON] = [FIRST_ANON_TEXT]
    st.session_state[S_USER] = []
    st.session_state[S_ERR] = None
    st.session_state[S_SAVED] = False
    st.session_state.pop(S_GDRIVE_RESULT, None)
    st.session_state[S_AUTOCOMPLETE] = ""
    st.session_state[S_POST_AUTOCOMPLETE] = ""
    if "s2_participant_id" in st.session_state:
        del st.session_state.s2_participant_id
    st.session_state.pop(S2_POST_AUTOFILL_DONE, None)
    st.session_state.pop(S2_REPLY_AUTOFILL_DONE, None)
    for k in list(st.session_state.keys()):
        ks = str(k)
        if ks.startswith("s2_reply_active_") or ks.startswith("s2_thought_draft") or ks == S2_REPLY_DRAFT_KEY:
            del st.session_state[k]


def _css() -> None:
    st.markdown(
        """
        <style>
        .s2-page-title {
            font-size: 2.15rem;
            font-weight: 700;
            margin: 0 0 0.35rem 0;
            padding: 0;
            line-height: 1.2;
        }
        .s2-post-box {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            background: #fafafa;
            margin: 0 0 1rem 0;
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


def _merge_autocomplete_into_draft(draft_key: str, suggestion: str) -> None:
    sug = (suggestion or "").strip()
    if not sug:
        return
    cur = (st.session_state.get(draft_key) or "").rstrip()
    if not cur:
        st.session_state[draft_key] = sug
    else:
        st.session_state[draft_key] = cur + " " + sug


def _ensure_post_autofill(thought_draft_key: str) -> None:
    """게시물 생각 입력란: 최초 1회 LLM 제안을 생성해 입력란에 반영."""
    if st.session_state.get(S2_POST_AUTOFILL_DONE):
        return
    st.session_state[S2_POST_AUTOFILL_DONE] = True
    draft_preview = (st.session_state.get(thought_draft_key) or "").strip()
    try:
        with st.spinner("입력 제안을 불러오는 중…"):
            prompt = _build_post_thought_autocomplete_prompt(draft_preview)
            sugg = _call_llm(
                prompt,
                system=AUTOCOMPLETE_SYSTEM_PROMPT,
                max_tokens=280,
                temperature=0.65,
            )
    except Exception as e:
        st.session_state[S_ERR] = f"자동완성 오류: {e}"
        st.session_state[S_POST_AUTOCOMPLETE] = ""
        return
    if _llm_output_is_error(sugg):
        st.session_state[S_ERR] = sugg or "자동완성 제안을 만들지 못했습니다."
        st.session_state[S_POST_AUTOCOMPLETE] = ""
        return
    st.session_state[S_ERR] = None
    st.session_state[S_POST_AUTOCOMPLETE] = sugg.strip()
    _merge_autocomplete_into_draft(thought_draft_key, sugg)


def _ensure_reply_autofill(draft_key: str, anon: list[str], ai_body: str) -> None:
    """AI 댓글 응답 입력란: 최초 1회 LLM 제안을 생성해 입력란에 반영."""
    if st.session_state.get(S2_REPLY_AUTOFILL_DONE):
        return
    st.session_state[S2_REPLY_AUTOFILL_DONE] = True
    draft_preview = (st.session_state.get(draft_key) or "").strip()
    try:
        with st.spinner("응답 입력 제안을 불러오는 중…"):
            prompt = _build_reply_autocomplete_prompt(
                anon[0],
                ai_body,
                draft_preview,
                st.session_state.get(S_POST_THOUGHT) or "",
            )
            sugg = _call_llm(
                prompt,
                system=AUTOCOMPLETE_SYSTEM_PROMPT,
                max_tokens=280,
                temperature=0.65,
            )
    except Exception as e:
        st.session_state[S_ERR] = f"자동완성 오류: {e}"
        st.session_state[S_AUTOCOMPLETE] = ""
        return
    if _llm_output_is_error(sugg):
        st.session_state[S_ERR] = sugg or "자동완성 제안을 만들지 못했습니다."
        st.session_state[S_AUTOCOMPLETE] = ""
        return
    st.session_state[S_ERR] = None
    st.session_state[S_AUTOCOMPLETE] = sugg.strip()
    _merge_autocomplete_into_draft(draft_key, sugg)


def _ensure_second_anon_loaded() -> None:
    """댓글 페이지 진입 시 첫 익명만 있으면 LLM으로 두 번째 익명 댓글을 채움."""
    anon: list[str] = st.session_state[S_ANON]
    if len(anon) >= 2:
        return
    if len(anon) != 1:
        return
    if st.session_state.get(S_ERR):
        return
    try:
        with st.spinner("AI 에이전트의 익명 댓글을 준비하는 중…"):
            prompt = _build_llm_second_anon_prompt(anon[0], st.session_state.get(S_POST_THOUGHT) or "")
            next_anon = _call_llm(prompt)
        if _llm_output_is_error(next_anon):
            st.session_state[S_ERR] = next_anon or "댓글 생성에 실패했습니다. API 설정을 확인해 주세요."
            return
        _human_like_delay_before_show_comment(next_anon)
        anon.append(next_anon)
    except Exception as e:
        st.session_state[S_ERR] = f"LLM 호출 오류: {e}"


def _render_title_and_post() -> None:
    """제목과 게시물 본문을 한 번에 렌더해 사이 여백을 줄입니다."""
    body = html.escape(POST_BODY)
    st.markdown(
        f'<h1 class="s2-page-title">Study 2 테스트</h1>'
        f'<div class="s2-post-box" style="white-space:pre-wrap;">{body}</div>',
        unsafe_allow_html=True,
    )


def _render_anon_bubble(text: str) -> None:
    safe = html.escape(text)
    st.markdown(
        f'<div class="s2-anon-row">{_AVATAR_BOX}<p class="s2-anon-name">익명</p></div>'
        f'<div class="s2-comment-text">{safe}</div>',
        unsafe_allow_html=True,
    )


def _on_submit_current_turn(draft_key: str) -> None:
    text = (st.session_state.get(draft_key) or "").strip()
    if not text:
        st.session_state[S_ERR] = "응답을 한 글자 이상 입력해 주세요."
        return
    anon: list[str] = st.session_state[S_ANON]
    user: list[str] = st.session_state[S_USER]

    user.append(text)
    st.session_state[S_ERR] = None

    if _thread_complete(anon, user):
        try:
            _save_conversation_to_disk_and_drive()
            st.session_state[S_SAVED] = True
        except Exception as e:
            st.session_state[S_ERR] = f"저장/Drive 오류: {e}"
        st.rerun()
        return

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

    _render_title_and_post()

    if st.session_state[S_PAGE] == "post":
        _ensure_post_autofill("s2_thought_draft")
    else:
        _ensure_second_anon_loaded()

    if st.session_state[S_ERR]:
        st.error(st.session_state[S_ERR])

    if st.session_state[S_PAGE] == "post":
        st.subheader("이 게시물에 대해 어떻게 생각하시나요?")
        thought_draft_key = "s2_thought_draft"
        st.text_area(
            "게시물에 대한 생각",
            height=TEXTAREA_HEIGHT,
            key=thought_draft_key,
            placeholder="여기에 생각을 적어 주세요. 위 내용에 자동 제안이 붙었을 수 있습니다.",
            label_visibility="collapsed",
        )

        if st.button("다음", type="primary"):
            st.session_state[S_POST_THOUGHT] = st.session_state.get(thought_draft_key, "")
            st.session_state[S_PAGE] = "comments"
            st.session_state[S_ERR] = None
            st.rerun()
        return

    # --- 댓글 페이지: 두 번째 익명(AI)까지 로드 후, 그에 대한 응답 1회만 ---
    anon = st.session_state[S_ANON]
    user = st.session_state[S_USER]

    if len(anon) == 1 and st.session_state.get(S_ERR):
        st.markdown("---")
        _render_anon_bubble(anon[0])
        if st.button("AI 댓글 다시 불러오기"):
            st.session_state[S_ERR] = None
            st.rerun()
        return

    if len(anon) < 2:
        st.markdown("---")
        _render_anon_bubble(anon[0])
        st.caption("AI 에이전트의 익명 댓글을 준비하는 중입니다…")
        return

    st.markdown("---")
    _render_anon_bubble(anon[0])
    st.caption("첫 익명 댓글을 읽어 주세요. 이어서 AI 에이전트의 댓글이 표시됩니다.")

    st.markdown("---")
    _render_anon_bubble(anon[1])
    ai_body = anon[1]

    draft_key = S2_REPLY_DRAFT_KEY
    if len(user) >= 1:
        st.text_area(
            "응답 (제출됨)",
            value=user[0],
            height=TEXTAREA_HEIGHT,
            key="s2_reply_done_final",
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        _ensure_reply_autofill(draft_key, anon, ai_body)
        if st.session_state[S_ERR]:
            st.error(st.session_state[S_ERR])
        st.text_area(
            "AI 익명 댓글에 대한 응답",
            height=TEXTAREA_HEIGHT,
            key=draft_key,
            placeholder="여기에 응답을 적어 주세요. 위 내용에 자동 제안이 붙었을 수 있습니다.",
            label_visibility="collapsed",
        )

        if st.button("응답 제출 (한 번만)", type="primary"):
            _on_submit_current_turn(draft_key)

    if _thread_complete(anon, user):
        st.success("응답이 완료되어 설문을 종료합니다. 참여해 주셔서 감사합니다.")
        gd = st.session_state.get(S_GDRIVE_RESULT)
        if gd:
            ok, msg = gd
            if ok:
                st.info(msg)
            else:
                st.warning(msg)
        if st.button("처음부터 다시"):
            _reset_all()
            st.rerun()


if __name__ == "__main__":
    main()
