document.querySelector(".login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const inputs = document.querySelectorAll(".login-form .input");
  const email = inputs[0].value.trim();
  const password = inputs[1].value.trim();

  try {
    const response = await fetch("http://127.0.0.1:8080/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      alert(await response.text());
      return;
    }

    const token = await response.text();

    // 🔥 로그인 토큰 저장
    localStorage.setItem("token", token);

    // 메인 페이지 이동
    window.location.href = "../index.html";

  } catch (err) {
    alert("로그인 요청 실패");
    console.error(err);
  }
});
