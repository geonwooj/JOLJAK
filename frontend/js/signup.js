document.querySelector(".signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  console.log("signup.js loaded");


  const inputs = document.querySelectorAll(".signup-form .input");
  const name = inputs[0].value.trim();
  const email = inputs[1].value.trim();
  const password = inputs[2].value.trim();

  if (!name || !email || !password) {
    alert("모든 필드를 입력해주세요.");
    return;
  }

  try {
    const response = await fetch("http://127.0.0.1:8080/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password })
    });

    if (!response.ok) {
      const errMsg = await response.text();
      alert("회원가입 실패: " + errMsg);
      return;
    }

    const result = await response.text();
    alert("회원가입 성공: " + result);

    // 로그인 페이지로 이동
    window.location.href = "./login.html";

  } catch (err) {
    alert("회원가입 요청 실패. 서버 확인 필요.");
    console.error(err);
  }
});
