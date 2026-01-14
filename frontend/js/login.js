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

    // 실패 응답 처리
    if (!response.ok) {
      const errMsg = await response.text();
      await CustomModal.alert("로그인 실패: " + errMsg);
      return;
    }

    // ✅ 서버가 토큰 문자열(plain text)로 내려주는 경우: text()로 1번만 읽기
    const token = (await response.text()).trim();

    if (!token) {
      await CustomModal.alert("서버에서 토큰을 받지 못했습니다.");
      return;
    }

    // ✅ localStorage에 토큰 저장
    localStorage.setItem("token", token);

    await CustomModal.alert("로그인 성공!");

    // 메인 페이지로 이동
    window.location.href = "../index.html";
  } catch (err) {
    await CustomModal.alert("로그인 요청 실패. 서버 확인 필요.");
    console.error(err);
  }
});
