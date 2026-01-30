package com.joljak.backend.dto.chat;

import com.joljak.backend.domain.chat.ChatMessage;

import java.time.LocalDateTime;

public class ChatMessageResponse {

    private Long id;
    private String role; // USER / AI
    private String content;
    private LocalDateTime createdAt;

    public ChatMessageResponse(Long id, String role, String content, LocalDateTime createdAt) {
        this.id = id;
        this.role = role;
        this.content = content;
        this.createdAt = createdAt;
    }

    public static ChatMessageResponse from(ChatMessage m) {
        return new ChatMessageResponse(
                m.getId(),
                m.getRole().name(),
                m.getContent(),
                m.getCreatedAt()
        );
    }

    public Long getId() { return id; }
    public String getRole() { return role; }
    public String getContent() { return content; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
