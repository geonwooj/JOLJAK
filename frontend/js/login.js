document.querySelector(".login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const inputs = document.querySelectorAll(".login-form .input");
  const email = inputs[0].value.trim();
  const password = inputs[1].value.trim();

  if (!email || !password) {
    await CustomModal.alert("이메일과 비밀번호를 입력해주세요.");
    return;
  }

  try {
    const response = await fetch("http://127.0.0.1:8080/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errMsg = await response.text();
      await CustomModal.alert("로그인 실패: " + errMsg);
      return;
    }

    const result = await response.text();
    await CustomModal.alert(result);

    // 🔥 로그인 토큰 저장
    localStorage.setItem("token", token);

    // 메인 페이지 이동
    window.location.href = "../index.html";
  } catch (err) {
    await CustomModal.alert("로그인 요청 실패. 서버 확인 필요.");
    console.error(err);
  }
});
