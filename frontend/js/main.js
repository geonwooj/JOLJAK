document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const btnLogin = document.getElementById("btnLogin");

  // 메시지 보내기 활성화/비활성
  function updateSendState() {
    const hasText = input.value.trim().length > 0;
    btnSend.disabled = !hasText;
  }

  input?.addEventListener("input", updateSendState);

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!btnSend.disabled) btnSend.click();
    }
  });

  btnSend?.addEventListener("click", () => {
    const text = input.value.trim();
    if (!text) return;

    console.log("send:", text);
    input.value = "";
    updateSendState();
  });

  // 로그인 상태 체크
  const token = localStorage.getItem("token");

  if (token) {
    // 로그인된 상태 → 버튼을 로그아웃으로 변경
    btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M6 18l12 -12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      로그아웃
    `;

    btnLogin.onclick = () => {
      localStorage.removeItem("token");
      alert("로그아웃되었습니다.");
      window.location.href = "./index.html";
    };
  } else {
    // 로그인 안 된 상태 → 로그인 페이지 이동
    btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path
          d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z"
          stroke="currentColor"
          stroke-width="1.8"
        />
        <path
          d="M4 20a8 8 0 0 1 16 0"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
        />
      </svg>
      로그인 하세요
    `;

    btnLogin.onclick = () => {
      window.location.href = "./pages/login.html";
    };
  }

  // 사이드바 토글
  const app = document.querySelector(".app");
  const btnMenu = document.getElementById("btnMenu");

  btnMenu?.addEventListener("click", () => {
    app.classList.toggle("is-collapsed");
  });
});
