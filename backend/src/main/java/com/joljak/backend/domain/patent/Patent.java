package com.joljak.backend.domain.patent;

import jakarta.persistence.*;

/**
 * 원본 특허 DB
 *
 * - 특허 이름
 * - 특허 종류
 * - KorPatBERT 결과 .npy 경로
 * - 특허 원문 저장소 참조(FK)
 */
@Entity
@Table(name = "patents")
public class Patent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "title", nullable = false)
    private String title;

    @Enumerated(EnumType.STRING)
    @Column(name = "category", nullable = false)
    private PatentCategory category;

    @Column(name = "embedding_npy_path", nullable = false, length = 2048)
    private String embeddingNpyPath;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "document_id", nullable = false)
    private PatentDocument document;

    protected Patent() {}

    public Patent(String title, PatentCategory category, String embeddingNpyPath, PatentDocument document) {
        this.title = title;
        this.category = category;
        this.embeddingNpyPath = embeddingNpyPath;
        this.document = document;
    }

    public Long getId() { return id; }
    public String getTitle() { return title; }
    public PatentCategory getCategory() { return category; }
    public String getEmbeddingNpyPath() { return embeddingNpyPath; }
    public PatentDocument getDocument() { return document; }

    public void setTitle(String title) { this.title = title; }
    public void setCategory(PatentCategory category) { this.category = category; }
    public void setEmbeddingNpyPath(String embeddingNpyPath) { this.embeddingNpyPath = embeddingNpyPath; }
    public void setDocument(PatentDocument document) { this.document = document; }
}
