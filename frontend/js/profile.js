document.addEventListener("DOMContentLoaded", async () => {
  const btnBack = document.getElementById("btnBack");
  const btnLogout = document.getElementById("btnLogout");
  const deleteAccountBtn = document.querySelector(".btn-danger");

  // 뒤로 가기
  btnBack.addEventListener("click", () => history.back());

  const token = localStorage.getItem("token");

  if (!token) {
    alert("로그인이 필요합니다.");
    window.location.href = "./login.html";
    return;
  }

  // ✅ 여기서 바로 프로필 로드
  try {
    const res = await fetch("http://127.0.0.1:8080/api/users/me", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) throw new Error("인증 실패");

    const data = await res.json();

    document.getElementById("userName").textContent = data.name;
    document.getElementById("userEmail").textContent = data.email;

    // 가입일 표시 (예: 2026. 1. 15.)
    const createdAtEl = document.getElementById("createdAt");
    if (createdAtEl) {
      if (data.createdAt) {
        const dt = new Date(data.createdAt);
        // Date 파싱 실패(Invalid Date) 대비
        if (!isNaN(dt.getTime())) {
          createdAtEl.textContent = dt.toLocaleDateString("ko-KR");
        } else {
          createdAtEl.textContent = data.createdAt; // 서버가 문자열로 주는 경우 fallback
        }
      } else {
        createdAtEl.textContent = "-";
      }
    }
  } catch (err) {
    console.error(err);
    alert("세션이 만료되었습니다. 다시 로그인해주세요.");
    localStorage.clear();
    window.location.href = "./login.html";
  }

  // 로그아웃
  btnLogout.addEventListener("click", async () => {
    localStorage.clear();
    alert("로그아웃 되었습니다.");
    window.location.href = "./login.html";
  });
});
