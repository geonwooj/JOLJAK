package com.joljak.backend.domain.patent;

import org.springframework.data.jpa.repository.JpaRepository;

public interface PatentDocumentRepository extends JpaRepository<PatentDocument, Long> {
}
