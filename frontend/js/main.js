// 아주 최소한의 동작만 넣어둠 (입력 시 전송 버튼 활성화, Enter 전송 등)

const input = document.getElementById("messageInput");
const btnSend = document.getElementById("btnSend");
const btnLogin = document.getElementById("btnLogin");

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

  // TODO: 나중에 백엔드 연결할 때 여기서 API 호출로 교체
  console.log("send:", text);

  input.value = "";
  updateSendState();
});

/* =========================
 * ⭐ 로그인 상태에 따라 버튼 변경
 * ========================= */
if (btnLogin) {
  const user = JSON.parse(localStorage.getItem("loginUser"));

  if (user && user.name) {
    // 🔐 로그인 상태
    btnLogin.lastChild.textContent = ` ${user.name}`;

    btnLogin.addEventListener("click", () => {
      location.href = "./pages/profile.html";
    });
  } else {
    // 🔓 비로그인 상태
    btnLogin.lastChild.textContent = " 로그인 하세요";

    btnLogin.addEventListener("click", () => {
      location.href = "./pages/login.html";
    });
  }
}

updateSendState();

// 사이드바 토글
const app = document.querySelector(".app");
const btnMenu = document.getElementById("btnMenu");

btnMenu?.addEventListener("click", () => {
  app.classList.toggle("is-collapsed");
});
