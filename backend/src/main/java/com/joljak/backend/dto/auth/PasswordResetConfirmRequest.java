package com.joljak.backend.dto.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public class PasswordResetConfirmRequest {
    @NotBlank @Email
    private String email;
    @NotBlank(message = "인증코드를 입력해주세요.")
    private String code;
    @NotBlank(message = "새 비밀번호를 입력해주세요.")
    private String newPassword;

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }
    public String getNewPassword() { return newPassword; }
    public void setNewPassword(String newPassword) { this.newPassword = newPassword; }
}
