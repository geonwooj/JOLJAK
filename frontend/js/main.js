document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const btnLogin = document.getElementById("btnLogin");

  // 메시지 보내기 활성화/비활성
  function updateSendState() {
    const hasText = input?.value?.trim().length > 0;
    if (btnSend) btnSend.disabled = !hasText;
  }

  input?.addEventListener("input", updateSendState);

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (btnSend && !btnSend.disabled) btnSend.click();
    }
  });

  btnSend?.addEventListener("click", () => {
    const text = input.value.trim();
    if (!text) return;

    console.log("send:", text);
    input.value = "";
    updateSendState();
  });

  function setLoggedOutUI() {
    if (!btnLogin) return;

    btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z" stroke="currentColor" stroke-width="1.8" />
        <path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
      로그인 하세요
    `;
    btnLogin.onclick = () => {
      window.location.href = "./pages/login.html";
    };
  }

  function setLoggedInUI(name) {
    if (!btnLogin) return;

    btnLogin.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z" stroke="currentColor" stroke-width="1.8" />
        <path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
      ${name}님 환영합니다.
    `;
    btnLogin.onclick = () => {
      window.location.href = "./pages/profile.html";
    };
  }

  // ✅ 앱 시작 시 토큰 검증: token이 있어도 /me 성공해야 "로그인"
  async function bootstrapAuth() {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoggedOutUI();
      return;
    }

    try {
      const res = await fetch("http://127.0.0.1:8080/api/users/me", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        localStorage.removeItem("token");
        localStorage.removeItem("userName");
        setLoggedOutUI();
        return;
      }

      const me = await res.json();
      const name = me?.name || "사용자";

      localStorage.setItem("userName", name);
      setLoggedInUI(name);
    } catch (e) {
      // 서버 꺼짐/네트워크 오류 포함 → 토큰 믿지 말고 로그아웃 처리
      localStorage.removeItem("token");
      localStorage.removeItem("userName");
      setLoggedOutUI();
    }
  }

  bootstrapAuth();

  // 사이드바 토글
  const app = document.querySelector(".app");
  const btnMenu = document.getElementById("btnMenu");

  btnMenu?.addEventListener("click", () => {
    app.classList.toggle("is-collapsed");
  });
});
