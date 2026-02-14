package com.joljak.backend.dto.auth;

public class SignupRequest {

    private String email;
    private String password;
    private String name;
    private boolean termsAccepted;

    public String getEmail() { return email; }
    public String getPassword() { return password; }
    public String getName() { return name; }
    public boolean isTermsAccepted() { return termsAccepted; }
}
