package com.joljak.backend.dto.chat;

import java.time.LocalDateTime;

public class ChatRoomResponse {

    private Long id;
    private String title;
    private LocalDateTime updatedAt;

    public ChatRoomResponse(Long id, String title, LocalDateTime updatedAt) {
        this.id = id;
        this.title = title;
        this.updatedAt = updatedAt;
    }

    public Long getId() { return id; }
    public String getTitle() { return title; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}
