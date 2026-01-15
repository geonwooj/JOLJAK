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

    // 실패 응답
    if (!response.ok) {
      const errMsg = await response.text();
      await CustomModal.alert("로그인 실패: " + errMsg);
      return;
    }

    // ✅ JSON으로 받기 (핵심)
    const data = await response.json();

    if (!data.token || !data.name) {
      await CustomModal.alert("로그인 응답이 올바르지 않습니다.");
      return;
    }

    // ✅ 저장
    localStorage.setItem("token", data.token);
    localStorage.setItem("userName", data.name);

    await CustomModal.alert("로그인 성공!");
    window.location.href = "../index.html";
  } catch (err) {
    console.error(err);
    await CustomModal.alert("로그인 요청 실패. 서버 확인 필요.");
  }
});
