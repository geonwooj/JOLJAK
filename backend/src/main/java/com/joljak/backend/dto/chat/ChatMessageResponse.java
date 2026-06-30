package com.joljak.backend.dto.chat;

import com.joljak.backend.domain.chat.ChatMessage;

import java.time.LocalDateTime;

public class ChatMessageResponse {

    private Long id;
    private String role;
    private String content;
    private String formattedContent;
    private String originalFileName;
    private String fileContentType;
    private Long fileSize;
    private LocalDateTime createdAt;

    public ChatMessageResponse(
            Long id,
            String role,
            String content,
            String formattedContent,
            String originalFileName,
            String fileContentType,
            Long fileSize,
            LocalDateTime createdAt
    ) {
        this.id = id;
        this.role = role;
        this.content = content;
        this.formattedContent = formattedContent;
        this.originalFileName = originalFileName;
        this.fileContentType = fileContentType;
        this.fileSize = fileSize;
        this.createdAt = createdAt;
    }

    // 기존 ChatController의 .map(ChatMessageResponse::from)과 호환용
    public static ChatMessageResponse from(ChatMessage m) {
        return from(m, null);
    }

    public static ChatMessageResponse from(ChatMessage m, String formattedContent) {
        return new ChatMessageResponse(
                m.getId(),
                m.getRole().name(),
                m.getContent(),
                formattedContent,
                m.getOriginalFileName(),
                m.getFileContentType(),
                m.getFileSize(),
                m.getCreatedAt()
        );
    }

    public Long getId() { return id; }
    public String getRole() { return role; }
    public String getContent() { return content; }
    public String getFormattedContent() { return formattedContent; }
    public String getOriginalFileName() { return originalFileName; }
    public String getFileContentType() { return fileContentType; }
    public Long getFileSize() { return fileSize; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
