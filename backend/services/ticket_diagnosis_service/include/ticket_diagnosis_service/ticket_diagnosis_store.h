#pragma once

#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include "ticket_diagnosis.pb.h"

namespace robotops::ticket_diagnosis_service {

struct TicketListFilter {
    int page = 1;
    int page_size = 20;
    robotops::common::RobotType robot_type = robotops::common::ROBOT_TYPE_UNSPECIFIED;
    std::string main_module;
    std::string status;
    std::string keyword;
};

class TicketDiagnosisStore {
public:
    robotops::ticket_diagnosis::BugTicket createTicket(
        const robotops::ticket_diagnosis::CreateBugTicketRequest& request);

    std::optional<robotops::ticket_diagnosis::BugTicket> getTicket(const std::string& bug_id) const;

    std::vector<robotops::ticket_diagnosis::BugTicket> listTickets(
        const TicketListFilter& filter,
        int64_t* total) const;

    robotops::ticket_diagnosis::DiagnosisTask createDiagnosisTask(
        const std::string& bug_id,
        const std::string& agent_request_id);

    std::optional<robotops::ticket_diagnosis::DiagnosisTask> getDiagnosisTask(
        const std::string& task_id) const;

    std::optional<robotops::ticket_diagnosis::DiagnosisTask> updateDiagnosisTask(
        const std::string& task_id,
        robotops::common::TaskStatus status,
        const std::string& message);

    robotops::ticket_diagnosis::DiagnosisReport saveReport(
        const robotops::ticket_diagnosis::DiagnosisReport& request_report);

    std::optional<robotops::ticket_diagnosis::DiagnosisReport> getReport(
        const std::string& report_id,
        const std::string& task_id,
        const std::string& bug_id) const;

private:
    static std::string makeId(const std::string& prefix, int64_t sequence);
    static int64_t currentUnixMillis();
    static bool ticketMatches(
        const robotops::ticket_diagnosis::BugTicket& ticket,
        const TicketListFilter& filter);
    static bool containsCaseInsensitive(const std::string& value, const std::string& keyword);
    static int normalizePage(int page);
    static int normalizePageSize(int page_size);

private:
    mutable std::mutex mutex_;
    int64_t bug_sequence_ = 0;
    int64_t task_sequence_ = 0;
    int64_t report_sequence_ = 0;
    std::map<std::string, robotops::ticket_diagnosis::BugTicket> tickets_;
    std::vector<std::string> ticket_order_;
    std::map<std::string, robotops::ticket_diagnosis::DiagnosisTask> tasks_;
    std::vector<std::string> task_order_;
    std::map<std::string, robotops::ticket_diagnosis::DiagnosisReport> reports_;
    std::vector<std::string> report_order_;
};

} // namespace robotops::ticket_diagnosis_service
