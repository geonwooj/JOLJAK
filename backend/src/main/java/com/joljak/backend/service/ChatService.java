package com.joljak.backend.service;

import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.domain.chat.ChatMessageRepository;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.domain.chat.ChatRoomRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

@Service
public class ChatService {

    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AiService aiService;
    private final SignalService signalService;
    private final TransactionTemplate transactionTemplate;

    // AI 모델은 메모리를 많이 먹기 때문에 동시에 여러 개 실행하지 않도록 1개씩만 처리
    private final ExecutorService aiExecutor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r);
        thread.setName("ai-worker");
        thread.setDaemon(true);
        return thread;
    });

    @Value("${file.upload-dir:uploads/chat}")
    private String uploadDir;

    public ChatService(
            ChatRoomRepository chatRoomRepository,
            ChatMessageRepository chatMessageRepository,
            AiService aiService,
            SignalService signalService,
            PlatformTransactionManager transactionManager) {
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.aiService = aiService;
        this.signalService = signalService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage) {
        return startChat(userEmail, firstMessage, null);
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage, MultipartFile file) {
        validateMessageOrFile(firstMessage, file);

        SavedFile savedFile = saveFileIfExists(file);
        String normalizedMessage = normalizeMessage(firstMessage, savedFile);
        String title = makeTitle(normalizedMessage);

        ChatRoom room = chatRoomRepository.save(new ChatRoom(userEmail, title));
        chatMessageRepository.save(createUserMessage(room, userEmail, normalizedMessage, savedFile));

        String savedFilePath = savedFile != null ? savedFile.filePath : null;
        String aiInput = makeAiInput(firstMessage);

        signalService.start(room.getId(), userEmail);
        runAiAfterCommit(room.getId(), userEmail, aiInput, savedFilePath);

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

        SavedFile savedFile = saveFileIfExists(file);
        String normalizedMessage = normalizeMessage(message, savedFile);
        chatMessageRepository.save(createUserMessage(room, userEmail, normalizedMessage, savedFile));

        String savedFilePath = savedFile != null ? savedFile.filePath : null;
        String aiInput = makeAiInput(message);

        signalService.start(room.getId(), userEmail);
        runAiAfterCommit(room.getId(), userEmail, aiInput, savedFilePath);

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

    private void runAiAfterCommit(Long roomId, String userEmail, String aiInput, String savedFilePath) {
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                aiExecutor.submit(() -> generateAndSaveAiAnswer(roomId, userEmail, aiInput, savedFilePath));
            }
        });
    }

    private void generateAndSaveAiAnswer(Long roomId, String userEmail, String aiInput, String savedFilePath) {
        String aiAnswer = null;

        try {
            aiAnswer = aiService.generateAnswer(aiInput, savedFilePath, roomId);

            final String answerToSave = safeAnswer(aiAnswer);

            transactionTemplate.executeWithoutResult(status -> {
                ChatRoom room = chatRoomRepository.findById(roomId)
                        .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

                chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, answerToSave));
                room.touch();
            });

            signalService.finish(roomId);
        } catch (Exception e) {
            String errorMessage = "AI 답변 생성 중 오류가 발생했습니다.";

            transactionTemplate.executeWithoutResult(status -> {
                chatRoomRepository.findById(roomId).ifPresent(room -> {
                    chatMessageRepository.save(new ChatMessage(room, ChatMessage.Role.AI, userEmail, errorMessage));
                    room.touch();
                });
            });

            signalService.fail(roomId, errorMessage);
        } finally {
            aiAnswer = null;
        }
    }

    private String safeAnswer(String aiAnswer) {
        if (aiAnswer == null || aiAnswer.trim().isEmpty()) {
            return "AI 답변이 비어 있습니다.";
        }
        return aiAnswer.trim();
    }

    private void validateMessageOrFile(String message, MultipartFile file) {
        boolean hasMessage = message != null && !message.trim().isEmpty();
        boolean hasFile = file != null && !file.isEmpty();

        if (!hasMessage && !hasFile) {
            throw new IllegalArgumentException("메시지 또는 파일을 입력해주세요.");
        }
    }

    private String normalizeMessage(String message, SavedFile savedFile) {
        String trimmed = message == null ? "" : message.trim();
        if (!trimmed.isEmpty()) {
            return trimmed;
        }

        if (savedFile != null) {
            return "파일을 첨부했습니다: " + savedFile.originalFileName;
        }

        return "";
    }

    private String makeAiInput(String message) {
        return message == null ? "" : message.trim();
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
                savedFile.fileSize);
    }

    private SavedFile saveFileIfExists(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            return null;
        }

        try {
            Path dir = Paths.get(uploadDir).toAbsolutePath().normalize();
            Files.createDirectories(dir);

            String originalFileName = StringUtils.cleanPath(
                    file.getOriginalFilename() == null ? "file" : file.getOriginalFilename());

            String extension = "";
            int dotIndex = originalFileName.lastIndexOf('.');
            if (dotIndex >= 0) {
                extension = originalFileName.substring(dotIndex);
            }

            String storedFileName = UUID.randomUUID() + extension;
            Path target = dir.resolve(storedFileName).normalize();

            Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);

            return new SavedFile(
                    originalFileName,
                    storedFileName,
                    target.toString(),
                    file.getContentType(),
                    file.getSize());
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

    @PreDestroy
    public void shutdownAiExecutor() {
        aiExecutor.shutdownNow();
        try {
            aiExecutor.awaitTermination(3, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static class SavedFile {
        private final String originalFileName;
        private final String storedFileName;
        private final String filePath;
        private final String contentType;
        private final Long fileSize;

        private SavedFile(
                String originalFileName,
                String storedFileName,
                String filePath,
                String contentType,
                Long fileSize) {
            this.originalFileName = originalFileName;
            this.storedFileName = storedFileName;
            this.filePath = filePath;
            this.contentType = contentType;
            this.fileSize = fileSize;
        }
    }
}