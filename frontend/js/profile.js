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
