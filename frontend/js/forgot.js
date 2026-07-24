document.getElementById("forgotForm").addEventListener("submit", function (e) {
  e.preventDefault();

  const email = document.getElementById("emailInput").value.trim();

  if (!email) {
    alert("이메일을 입력해주세요.");
    return;
  }

  // TODO: 서버에 재설정 요청 보내기
  alert("재설정 링크가 전송되었습니다.");
});
