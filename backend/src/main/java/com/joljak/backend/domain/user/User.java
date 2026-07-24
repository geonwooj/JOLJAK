package com.joljak.backend.domain.user;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(nullable = false)
    private String password;

    @Column(nullable = false)
    private String name;

    // ✅ 이메일 인증 여부
    @Column(nullable = false)
    private boolean emailVerified;

    // ✅ 가입일(계정 생성 시각)
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected User() {}

    public User(String email, String password, String name, boolean emailVerified) {
        this.email = email;
        this.password = password;
        this.name = name;
        this.emailVerified = emailVerified;
    }

    // ✅ DB 저장 직전에 자동으로 가입일 세팅
    @PrePersist
    protected void onCreate() {
        if (this.createdAt == null) {
            this.createdAt = LocalDateTime.now();
        }
    }

    public Long getId() { return id; }
    public String getEmail() { return email; }
    public String getPassword() { return password; }
    public String getName() { return name; }
    public boolean isEmailVerified() { return emailVerified; }
    public LocalDateTime getCreatedAt() { return createdAt; }

    public void setEmailVerified(boolean emailVerified) { this.emailVerified = emailVerified; }
}
