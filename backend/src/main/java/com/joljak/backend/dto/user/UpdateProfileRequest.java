package com.joljak.backend.dto.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class UpdateProfileRequest {
    @NotBlank(message = "이름을 입력해주세요.")
    @Size(max = 30, message = "이름은 30자 이하로 입력해주세요.")
    private String name;

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
}
