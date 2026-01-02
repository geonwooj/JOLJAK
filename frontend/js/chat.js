// 채팅 입력: 텍스트 있으면 전송 버튼 활성화 + Enter 전송
const input = document.getElementById("messageInput");
const btnSend = document.getElementById("btnSend");
const btnLogin = document.getElementById("btnLogin");
const chatWrap = document.getElementById("chatWrap");

function updateSendState() {
  const hasText = input.value.trim().length > 0;
  btnSend.disabled = !hasText;
}

input.addEventListener("input", updateSendState);

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    if (!btnSend.disabled) btnSend.click();
  }
});

btnSend.addEventListener("click", () => {
  const text = input.value.trim();
  if (!text) return;

  // ✅ 데모용: 사용자가 보낸 메시지를 Q로 추가 (나중에 API로 교체)
  const q = document.createElement("div");
  q.className = "msg msg--q";
  q.innerHTML = `
    <div class="msg__avatar msg__avatar--q" aria-hidden="true">Q</div>
    <div class="msg__bubble"><div class="msg__title"></div></div>
  `;
  q.querySelector(".msg__title").textContent = text;
  chatWrap.appendChild(q);

  input.value = "";
  updateSendState();

  // 스크롤 맨 아래
  chatWrap.parentElement.scrollTo({
    top: chatWrap.parentElement.scrollHeight,
    behavior: "smooth",
  });

  // ✅ 데모용: AI 응답 흉내 (나중에 백엔드 연결)
  setTimeout(() => {
    const a = document.createElement("div");
    a.className = "msg msg--a";
    a.innerHTML = `
      <div class="msg__avatar msg__avatar--a" aria-hidden="true">A</div>
      <div class="msg__bubble msg__bubble--a">
        <div class="msg__text">데모 응답입니다. (나중에 AI/백엔드 연결)</div>
      </div>
    `;
    chatWrap.appendChild(a);
    chatWrap.parentElement.scrollTo({
      top: chatWrap.parentElement.scrollHeight,
      behavior: "smooth",
    });
  }, 400);
});

if (btnLogin) {
  btnLogin.addEventListener("click", () => {
    location.href = "./login.html";
  });
}

// 사이드바 토글
const app = document.getElementById("app");
const btnMenu = document.getElementById("btnMenu");
btnMenu?.addEventListener("click", () => app.classList.toggle("is-collapsed"));

updateSendState();
