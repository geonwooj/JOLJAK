package com.joljak.backend.domain.patent;

import jakarta.persistence.*;

/**
 * 특허 원문 저장소
 *
 * - 원문 이름
 * - 특허 PDF(파일 경로/URL)
 * - 특허 종류
 */
@Entity
@Table(name = "patent_documents")
public class PatentDocument {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "document_name", nullable = false)
    private String documentName;

    // PDF 파일 자체를 DB에 넣지 않고, 보통 파일 경로/URL만 저장
    @Column(name = "pdf_path", nullable = false, length = 2048)
    private String pdfPath;

    @Enumerated(EnumType.STRING)
    @Column(name = "category", nullable = false)
    private PatentCategory category;

    protected PatentDocument() {}

    public PatentDocument(String documentName, String pdfPath, PatentCategory category) {
        this.documentName = documentName;
        this.pdfPath = pdfPath;
        this.category = category;
    }

    public Long getId() { return id; }
    public String getDocumentName() { return documentName; }
    public String getPdfPath() { return pdfPath; }
    public PatentCategory getCategory() { return category; }

    public void setDocumentName(String documentName) { this.documentName = documentName; }
    public void setPdfPath(String pdfPath) { this.pdfPath = pdfPath; }
    public void setCategory(PatentCategory category) { this.category = category; }
}
