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

    @Column(name = "original_file_name")
    private String originalFileName;

    @Column(name = "stored_file_name")
    private String storedFileName;

    @Column(name = "file_path")
    private String filePath;

    @Column(name = "file_content_type")
    private String fileContentType;

    @Column(name = "file_size")
    private Long fileSize;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected ChatMessage() {}

    public ChatMessage(ChatRoom room, Role role, String userEmail, String content) {
        this.room = room;
        this.role = role;
        this.userEmail = userEmail;
        this.content = content;
    }

    public ChatMessage(
            ChatRoom room,
            Role role,
            String userEmail,
            String content,
            String originalFileName,
            String storedFileName,
            String filePath,
            String fileContentType,
            Long fileSize
    ) {
        this.room = room;
        this.role = role;
        this.userEmail = userEmail;
        this.content = content;
        this.originalFileName = originalFileName;
        this.storedFileName = storedFileName;
        this.filePath = filePath;
        this.fileContentType = fileContentType;
        this.fileSize = fileSize;
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
    public String getOriginalFileName() { return originalFileName; }
    public String getStoredFileName() { return storedFileName; }
    public String getFilePath() { return filePath; }
    public String getFileContentType() { return fileContentType; }
    public Long getFileSize() { return fileSize; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
