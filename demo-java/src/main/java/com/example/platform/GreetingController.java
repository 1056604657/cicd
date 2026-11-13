package com.example.platform;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class GreetingController {
    private final String message;
    private final String version;

    public GreetingController(@Value("${app.message}") String message,
                              @Value("${app.version}") String version) {
        this.message = message;
        this.version = version;
    }

    @GetMapping("/api/greeting")
    public Map<String, String> greeting(@RequestParam(defaultValue = "world") String name) {
        if (name.isBlank() || name.length() > 64) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "name must contain 1-64 characters");
        }
        return Map.of("message", message + ", " + name, "version", version);
    }
}
