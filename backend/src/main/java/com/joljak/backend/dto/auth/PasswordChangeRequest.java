package com.joljak.backend.dto.auth;

public class PasswordChangeRequest {
    private String currentPassword;
    private String newPassword;

    public String getCurrentPassword() { return currentPassword; }
    public String getNewPassword() { return newPassword; }
}
