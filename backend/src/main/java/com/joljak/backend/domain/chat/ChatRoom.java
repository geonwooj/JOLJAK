package com.joljak.backend.domain.chat;

import jakarta.persistence.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "chat_rooms")
public class ChatRoom {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_email", nullable = false)
    private String userEmail;

    // 사이드바에 보여줄 제목(첫 질문 일부)
    @Column(nullable = false)
    private String title;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    protected ChatRoom() {}

    public ChatRoom(String userEmail, String title) {
        this.userEmail = userEmail;
        this.title = title;
    }

    @PrePersist
    protected void onCreate() {
        LocalDateTime now = LocalDateTime.now();
        if (createdAt == null) createdAt = now;
        if (updatedAt == null) updatedAt = now;
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    public void touch() {
        this.updatedAt = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public String getUserEmail() { return userEmail; }
    public String getTitle() { return title; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }

    public void setTitle(String title) { this.title = title; }
}
