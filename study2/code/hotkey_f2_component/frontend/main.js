/**
 * Minimal Streamlit component: iframe 포커스 상태에서 target_key(기본 F2) 입력 시
 * Streamlit에 "accept" 값을 보냅니다.
 */
function onRender(event) {
  const args = event.detail.args || {};
  const targetKey = args.target_key || "F2";
  const hintText = args.hint_text || "";
  const body = document.body;
  body.innerHTML = "";

  const wrap = document.createElement("div");
  wrap.className = "s2-hotkey-wrap";

  const hint = document.createElement("div");
  hint.className = "s2-hotkey-hint";
  hint.textContent = hintText;

  const sub = document.createElement("div");
  sub.className = "s2-hotkey-sub";
  sub.textContent =
    "이 회색 영역을 한 번 클릭한 뒤 키보드의 " +
    targetKey +
    " 키를 누르면, 아래 응답 입력란에 [AI 제안]의 첫 단어가 채워집니다.";

  wrap.appendChild(hint);
  wrap.appendChild(sub);
  body.appendChild(wrap);

  function onKeyDown(e) {
    const k = e.key;
    if (k === targetKey || (targetKey === "F2" && e.code === "F2")) {
      e.preventDefault();
      Streamlit.setComponentValue("accept");
    }
  }

  if (window._s2HotkeyHandler) {
    document.removeEventListener("keydown", window._s2HotkeyHandler);
  }
  window._s2HotkeyHandler = onKeyDown;
  document.addEventListener("keydown", onKeyDown);

  Streamlit.setFrameHeight(88);
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
