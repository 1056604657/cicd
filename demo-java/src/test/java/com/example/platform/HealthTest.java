package com.example.platform;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = "management.server.port=0")
class HealthTest {
    @Autowired TestRestTemplate rest;
    @Test void exposesReadinessOnApplicationPort() {
        var response = rest.getForEntity("/readyz", String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(response.getBody()).contains("UP");
    }
    @Test void doesNotExposeManagementOnApplicationPort() {
        assertThat(rest.getForEntity("/actuator/prometheus", String.class)
            .getStatusCode().value()).isEqualTo(404);
    }
}
