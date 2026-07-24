package com.joljak.backend.controller;

import com.joljak.backend.config.JwtUtil;
import com.joljak.backend.domain.user.User;
import com.joljak.backend.dto.user.ChangePasswordRequest;
import com.joljak.backend.dto.user.UpdateProfileRequest;
import com.joljak.backend.service.AuthService;
import io.jsonwebtoken.JwtException;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/users")
public class UserController {
    private final AuthService authService;
    private final JwtUtil jwtUtil;

    public UserController(AuthService authService, JwtUtil jwtUtil) {
        this.authService = authService;
        this.jwtUtil = jwtUtil;
    }

    @GetMapping("/me")
    public ResponseEntity<?> getMyInfo(@RequestHeader(value = "Authorization", required = false) String header) {
        try {
            User user = authService.findByEmail(extractEmail(header));
            return ResponseEntity.ok(Map.of("name", user.getName(), "email", user.getEmail(), "createdAt", user.getCreatedAt()));
        } catch (JwtException | IllegalArgumentException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        }
    }

    @PatchMapping("/me")
    public ResponseEntity<?> updateProfile(@RequestHeader(value = "Authorization", required = false) String header,
                                           @Valid @RequestBody UpdateProfileRequest request) {
        try {
            User user = authService.updateProfile(extractEmail(header), request.getName());
            return ResponseEntity.ok(Map.of("message", "프로필이 변경되었습니다.", "name", user.getName()));
        } catch (JwtException | IllegalArgumentException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @PatchMapping("/me/password")
    public ResponseEntity<?> changePassword(@RequestHeader(value = "Authorization", required = false) String header,
                                            @Valid @RequestBody ChangePasswordRequest request) {
        try {
            authService.changePassword(extractEmail(header), request.getCurrentPassword(), request.getNewPassword());
            return ResponseEntity.ok("비밀번호가 변경되었습니다.");
        } catch (JwtException | IllegalArgumentException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @DeleteMapping("/me")
    public ResponseEntity<?> deleteMyAccount(@RequestHeader(value = "Authorization", required = false) String header) {
        try {
            authService.deleteUserByEmail(extractEmail(header));
            return ResponseEntity.ok("계정이 삭제되었습니다.");
        } catch (JwtException | IllegalArgumentException e) {
            return ResponseEntity.status(401).body("Unauthorized");
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    private String extractEmail(String header) {
        if (header == null || !header.startsWith("Bearer ")) throw new JwtException("Unauthorized");
        String token = header.substring(7).trim();
        if (token.isBlank()) throw new JwtException("Unauthorized");
        return jwtUtil.extractEmail(token);
    }
}
