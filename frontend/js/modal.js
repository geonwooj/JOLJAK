const CustomModal = {
  // 모달을 동적으로 생성하여 바디에 삽입
  init() {
    if (document.getElementById("customModal")) return;

    const modalHtml = `
      <div id="customModal" class="modal-overlay">
        <div class="modal-content">
          <p id="modalMessage" class="modal-message"></p>
          <div class="modal-buttons">
            <button id="modalCancelBtn" class="modal-btn modal-btn-cancel" style="display:none;">취소</button>
            <button id="modalConfirmBtn" class="modal-btn modal-btn-confirm">확인</button>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  },

  // 알림창 (Alert 대체)
  alert(message) {
    this.init();
    return new Promise((resolve) => {
      const modal = document.getElementById("customModal");
      document.getElementById("modalMessage").innerText = message;
      document.getElementById("modalCancelBtn").style.display = "none";
      modal.style.display = "flex";

      document.getElementById("modalConfirmBtn").onclick = () => {
        modal.style.display = "none";
        resolve(true);
      };
    });
  },

  // 확인창 (Confirm 대체)
  confirm(message) {
    this.init();
    return new Promise((resolve) => {
      const modal = document.getElementById("customModal");
      document.getElementById("modalMessage").innerText = message;
      document.getElementById("modalCancelBtn").style.display = "block";
      modal.style.display = "flex";

      document.getElementById("modalConfirmBtn").onclick = () => {
        modal.style.display = "none";
        resolve(true);
      };
      document.getElementById("modalCancelBtn").onclick = () => {
        modal.style.display = "none";
        resolve(false);
      };
    });
  },
};
