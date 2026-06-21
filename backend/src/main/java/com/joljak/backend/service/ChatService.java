package com.joljak.backend.service;

import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.domain.chat.ChatMessageRepository;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.domain.chat.ChatRoomRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.UUID;

@Service
public class ChatService {

    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final ChatAiWorker chatAiWorker;

    @Value("${file.upload-dir:uploads/chat}")
    private String uploadDir;

    public ChatService(
            ChatRoomRepository chatRoomRepository,
            ChatMessageRepository chatMessageRepository,
            ChatAiWorker chatAiWorker
    ) {
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.chatAiWorker = chatAiWorker;
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage) {
        return startChat(userEmail, firstMessage, null);
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage, MultipartFile file) {
        validateMessageOrFile(firstMessage, file);

        String normalizedMessage = normalizeMessage(firstMessage, file);
        String title = makeTitle(normalizedMessage);
        ChatRoom room = chatRoomRepository.save(new ChatRoom(userEmail, title));

        SavedFile savedFile = saveFileIfExists(file);
        chatMessageRepository.save(createUserMessage(room, userEmail, normalizedMessage, savedFile));

        String savedFilePath = savedFile != null ? savedFile.filePath : null;
        runAiAfterCommit(room.getId(), userEmail, normalizedMessage, savedFilePath);

        room.touch();
        return room;
    }

    @Transactional
    public List<ChatMessage> addUserMessage(Long roomId, String userEmail, String message) {
        return addUserMessage(roomId, userEmail, message, null);
    }

    @Transactional
    public List<ChatMessage> addUserMessage(Long roomId, String userEmail, String message, MultipartFile file) {
        validateMessageOrFile(message, file);

        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        String normalizedMessage = normalizeMessage(message, file);
        SavedFile savedFile = saveFileIfExists(file);
        chatMessageRepository.save(createUserMessage(room, userEmail, normalizedMessage, savedFile));

        String savedFilePath = savedFile != null ? savedFile.filePath : null;
        runAiAfterCommit(room.getId(), userEmail, normalizedMessage, savedFilePath);

        room.touch();
        return chatMessageRepository.findByRoomIdOrderByCreatedAtAsc(roomId);
    }

    @Transactional(readOnly = true)
    public List<ChatRoom> recentRooms(String userEmail) {
        return chatRoomRepository.findTop5ByUserEmailOrderByUpdatedAtDesc(userEmail);
    }

    @Transactional(readOnly = true)
    public List<ChatMessage> getMessages(Long roomId, String userEmail) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        return chatMessageRepository.findByRoomIdOrderByCreatedAtAsc(roomId);
    }

    @Transactional
    public void deleteRoom(Long roomId, String userEmail) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        chatMessageRepository.deleteByRoomId(roomId);
        chatRoomRepository.delete(room);
    }

    private void runAiAfterCommit(Long roomId, String userEmail, String message, String savedFilePath) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    chatAiWorker.generateAndSaveAiAnswer(roomId, userEmail, message, savedFilePath);
                }
            });
            return;
        }

        chatAiWorker.generateAndSaveAiAnswer(roomId, userEmail, message, savedFilePath);
    }

    private void validateMessageOrFile(String message, MultipartFile file) {
        boolean hasMessage = message != null && !message.trim().isEmpty();
        boolean hasFile = file != null && !file.isEmpty();

        if (!hasMessage && !hasFile) {
            throw new IllegalArgumentException("메시지 또는 PDF 파일을 입력해주세요.");
        }

        if (hasFile && !isPdf(file)) {
            throw new IllegalArgumentException("PDF 파일만 첨부할 수 있습니다.");
        }
    }

    private boolean isPdf(MultipartFile file) {
        String originalFileName = file.getOriginalFilename() == null ? "" : file.getOriginalFilename().toLowerCase();
        String contentType = file.getContentType() == null ? "" : file.getContentType().toLowerCase();
        return originalFileName.endsWith(".pdf") || contentType.contains("pdf");
    }

    private String normalizeMessage(String message, MultipartFile file) {
        String trimmed = message == null ? "" : message.trim();
        if (!trimmed.isEmpty()) {
            return trimmed;
        }
        return "PDF 파일을 첨부했습니다: " + file.getOriginalFilename();
    }

    private ChatMessage createUserMessage(ChatRoom room, String userEmail, String content, SavedFile savedFile) {
        if (savedFile == null) {
            return new ChatMessage(room, ChatMessage.Role.USER, userEmail, content);
        }

        return new ChatMessage(
                room,
                ChatMessage.Role.USER,
                userEmail,
                content,
                savedFile.originalFileName,
                savedFile.storedFileName,
                savedFile.filePath,
                savedFile.contentType,
                savedFile.fileSize
        );
    }

    private SavedFile saveFileIfExists(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            return null;
        }

        try {
            Path dir = Paths.get(uploadDir).toAbsolutePath().normalize();
            Files.createDirectories(dir);

            String originalFileName = StringUtils.cleanPath(
                    file.getOriginalFilename() == null ? "file.pdf" : file.getOriginalFilename()
            );

            String extension = ".pdf";
            int dotIndex = originalFileName.lastIndexOf('.');
            if (dotIndex >= 0) {
                extension = originalFileName.substring(dotIndex);
            }

            String storedFileName = UUID.randomUUID() + extension;
            Path target = dir.resolve(storedFileName).normalize();

            if (!target.startsWith(dir)) {
                throw new IllegalArgumentException("잘못된 파일 경로입니다.");
            }

            Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);

            return new SavedFile(
                    originalFileName,
                    storedFileName,
                    target.toString(),
                    file.getContentType(),
                    file.getSize()
            );
        } catch (IOException e) {
            throw new IllegalArgumentException("파일 저장 중 오류가 발생했습니다.");
        }
    }

    private String makeTitle(String message) {
        String trimmed = message == null ? "" : message.trim();
        if (trimmed.isEmpty()) {
            return "새 채팅";
        }
        return trimmed.length() <= 20 ? trimmed : trimmed.substring(0, 20) + "…";
    }

    private static class SavedFile {
        private final String originalFileName;
        private final String storedFileName;
        private final String filePath;
        private final String contentType;
        private final Long fileSize;

        private SavedFile(String originalFileName, String storedFileName, String filePath, String contentType, Long fileSize) {
            this.originalFileName = originalFileName;
            this.storedFileName = storedFileName;
            this.filePath = filePath;
            this.contentType = contentType;
            this.fileSize = fileSize;
        }
    }
}
