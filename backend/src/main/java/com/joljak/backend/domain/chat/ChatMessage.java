package com.joljak.backend.domain.chat;

import jakarta.persistence.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "chat_messages")
public class ChatMessage {

    public enum Role {
        USER,
        AI
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "room_id", nullable = false)
    private ChatRoom room;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role;

    @Column(name = "user_email", nullable = false)
    private String userEmail;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String content;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected ChatMessage() {}

    public ChatMessage(ChatRoom room, Role role, String userEmail, String content) {
        this.room = room;
        this.role = role;
        this.userEmail = userEmail;
        this.content = content;
    }

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) createdAt = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public ChatRoom getRoom() { return room; }
    public Role getRole() { return role; }
    public String getUserEmail() { return userEmail; }
    public String getContent() { return content; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
