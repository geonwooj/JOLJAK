package com.joljak.backend.service;

import com.joljak.backend.domain.chat.ChatMessage;
import com.joljak.backend.domain.chat.ChatMessageRepository;
import com.joljak.backend.domain.chat.ChatRoom;
import com.joljak.backend.domain.chat.ChatRoomRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.concurrent.CompletableFuture;

@Service
public class ChatService {

    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AiService aiService;
    private final SignalService signalService;
    private final TransactionTemplate transactionTemplate;

    public ChatService(
            ChatRoomRepository chatRoomRepository,
            ChatMessageRepository chatMessageRepository,
            AiService aiService,
            SignalService signalService,
            PlatformTransactionManager transactionManager
    ) {
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.aiService = aiService;
        this.signalService = signalService;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    @Transactional
    public ChatRoom startChat(String userEmail, String firstMessage) {
        String title = makeTitle(firstMessage);

        ChatRoom room = chatRoomRepository.save(new ChatRoom(userEmail, title));

        chatMessageRepository.save(
                new ChatMessage(room, ChatMessage.Role.USER, userEmail, firstMessage)
        );

        room.touch();

        Long roomId = room.getId();

        signalService.start();

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                CompletableFuture.runAsync(() ->
                        generateAndSaveAiAnswer(roomId, userEmail, firstMessage)
                );
            }
        });

        return room;
    }

    @Transactional
    public List<ChatMessage> addUserMessage(Long roomId, String userEmail, String message) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

        if (!room.getUserEmail().equals(userEmail)) {
            throw new IllegalArgumentException("권한이 없습니다.");
        }

        chatMessageRepository.save(
                new ChatMessage(room, ChatMessage.Role.USER, userEmail, message)
        );

        room.touch();

        signalService.start();

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                CompletableFuture.runAsync(() ->
                        generateAndSaveAiAnswer(roomId, userEmail, message)
                );
            }
        });

        return chatMessageRepository.findByRoomIdOrderByCreatedAtAsc(roomId);
    }

    public void generateAndSaveAiAnswer(Long roomId, String userEmail, String message) {
        try {
            String aiAnswer = aiService.generateAnswer(message);

            transactionTemplate.executeWithoutResult(status -> {
                ChatRoom room = chatRoomRepository.findById(roomId)
                        .orElseThrow(() -> new IllegalArgumentException("채팅방이 존재하지 않습니다."));

                chatMessageRepository.save(
                        new ChatMessage(room, ChatMessage.Role.AI, userEmail, aiAnswer)
                );

                room.touch();
                chatRoomRepository.save(room);
            });

            signalService.finish();

        } catch (Exception e) {
            e.printStackTrace();

            signalService.fail("AI 답변 생성 중 오류가 발생했습니다.");

            transactionTemplate.executeWithoutResult(status -> {
                ChatRoom room = chatRoomRepository.findById(roomId).orElse(null);

                if (room != null) {
                    chatMessageRepository.save(
                            new ChatMessage(
                                    room,
                                    ChatMessage.Role.AI,
                                    userEmail,
                                    "AI 답변 생성 중 오류가 발생했습니다."
                            )
                    );

                    room.touch();
                    chatRoomRepository.save(room);
                }
            });
        }
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

    private String makeTitle(String message) {
        String trimmed = message == null ? "" : message.trim();

        if (trimmed.isEmpty()) {
            return "새 채팅";
        }

        return trimmed.length() <= 20 ? trimmed : trimmed.substring(0, 20) + "…";
    }
}