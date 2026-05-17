package com.joljak.backend.dto.chat;

import com.joljak.backend.domain.chat.ChatMessage;

import java.time.LocalDateTime;

public class ChatMessageResponse {

    private Long id;
    private String role;
    private String content;
    private String originalFileName;
    private String fileContentType;
    private Long fileSize;
    private LocalDateTime createdAt;

    public ChatMessageResponse(
            Long id,
            String role,
            String content,
            String originalFileName,
            String fileContentType,
            Long fileSize,
            LocalDateTime createdAt
    ) {
        this.id = id;
        this.role = role;
        this.content = content;
        this.originalFileName = originalFileName;
        this.fileContentType = fileContentType;
        this.fileSize = fileSize;
        this.createdAt = createdAt;
    }

    public static ChatMessageResponse from(ChatMessage m) {
        return new ChatMessageResponse(
                m.getId(),
                m.getRole().name(),
                m.getContent(),
                m.getOriginalFileName(),
                m.getFileContentType(),
                m.getFileSize(),
                m.getCreatedAt()
        );
    }

    public Long getId() { return id; }
    public String getRole() { return role; }
    public String getContent() { return content; }
    public String getOriginalFileName() { return originalFileName; }
    public String getFileContentType() { return fileContentType; }
    public Long getFileSize() { return fileSize; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
