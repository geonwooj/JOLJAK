package com.joljak.backend.domain.chat;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ChatRoomRepository extends JpaRepository<ChatRoom, Long> {

    // 최신순
    List<ChatRoom> findTop5ByUserEmailOrderByUpdatedAtDesc(String userEmail);
}
