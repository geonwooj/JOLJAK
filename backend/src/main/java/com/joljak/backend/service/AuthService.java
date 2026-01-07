package com.joljak.backend.service;

import com.joljak.backend.domain.user.User;
import com.joljak.backend.domain.user.UserRepository;
import com.joljak.backend.dto.auth.LoginRequest;
import com.joljak.backend.dto.auth.SignupRequest;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

    private final UserRepository userRepository;

    public AuthService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public User signup(SignupRequest request) {
        if (userRepository.findByEmail(request.getEmail()).isPresent()) {
            throw new RuntimeException("email already exists");
        }

        User user = new User(
                request.getEmail(),
                request.getPassword(),
                request.getName()
        );

        return userRepository.save(user);
    }

    public User login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new RuntimeException("user not found"));

        if (!user.getPassword().equals(request.getPassword())) {
            throw new RuntimeException("password mismatch");
        }

        return user;
    }
}
