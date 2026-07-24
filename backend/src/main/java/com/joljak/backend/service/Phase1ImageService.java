package com.joljak.backend.service;

import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Comparator;
import java.util.Optional;
import java.util.stream.Stream;

@Service
public class Phase1ImageService {

    private static final String IMAGE_FILE_NAME = "phase1_similarity_dashboard.png";

    public Optional<Resource> findPhase1Image(Long chatId) {
        try {
            Path backendDir = Path.of(System.getProperty("user.dir")).toAbsolutePath();
            Path projectRoot = backendDir.getParent();
            Path aiDir = projectRoot.resolve("ai");

            Optional<Path> latest = findLatestImage(aiDir);
            if (latest.isEmpty()) {
                return Optional.empty();
            }

            Path imagePath = latest.get();

            if (chatId != null) {
                Path cacheDir = backendDir.resolve("generated").resolve("phase1");
                Files.createDirectories(cacheDir);

                Path cached = cacheDir.resolve("chat_" + chatId + ".png");

                /*
                 * 기존 코드 문제:
                 * cached 파일이 있으면 무조건 그걸 반환해서,
                 * AI가 새 이미지를 만들어도 웹에는 예전 이미지가 계속 보였음.
                 *
                 * 수정:
                 * 항상 최신 phase1 이미지를 chat별 캐시로 덮어쓴다.
                 */
                Files.copy(imagePath, cached, StandardCopyOption.REPLACE_EXISTING);
                imagePath = cached;
            }

            return Optional.of(new FileSystemResource(imagePath));

        } catch (IOException e) {
            System.err.println("Phase 1 이미지 조회 실패: " + e.getMessage());
            return Optional.empty();
        }
    }

    private Optional<Path> findLatestImage(Path aiDir) throws IOException {
        if (!Files.isDirectory(aiDir)) {
            return Optional.empty();
        }

        try (Stream<Path> paths = Files.walk(aiDir, 8)) {
            return paths
                    .filter(Files::isRegularFile)
                    .filter(this::isPhase1Image)
                    .max(Comparator.comparingLong(this::lastModified));
        }
    }

    private boolean isPhase1Image(Path path) {
        String name = path.getFileName().toString().toLowerCase();
        return name.equals(IMAGE_FILE_NAME)
                || (name.startsWith("phase1") && name.endsWith(".png"));
    }

    private long lastModified(Path path) {
        try {
            return Files.getLastModifiedTime(path).toMillis();
        } catch (IOException e) {
            return 0L;
        }
    }
}