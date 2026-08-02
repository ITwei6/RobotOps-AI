#pragma once

#include <string>

#include "ticket_diagnosis.pb.h"

namespace robotops::ticket_diagnosis_service {

struct AgentDiagnosisResult {
    bool ok = false;
    int http_status = 0;
    std::string message;
    robotops::ticket_diagnosis::DiagnosisReport report;
};

class AgentClient {
public:
    explicit AgentClient(std::string default_endpoint, int timeout_ms = 300000);

    AgentDiagnosisResult diagnose(
        const robotops::ticket_diagnosis::BugTicket& ticket,
        const robotops::ticket_diagnosis::DiagnosisTask& task,
        const robotops::ticket_diagnosis::RunDiagnosisRequest& request) const;

private:
    std::string endpointOrDefault(const std::string& endpoint) const;

private:
    std::string default_endpoint_;
    int timeout_ms_;
};

} // namespace robotops::ticket_diagnosis_service
