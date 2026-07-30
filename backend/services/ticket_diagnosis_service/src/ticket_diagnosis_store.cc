#include "ticket_diagnosis_service/ticket_diagnosis_store.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <iomanip>
#include <sstream>

namespace robotops::ticket_diagnosis_service {

robotops::ticket_diagnosis::BugTicket TicketDiagnosisStore::createTicket(
    const robotops::ticket_diagnosis::CreateBugTicketRequest& request) {
    std::lock_guard<std::mutex> lock(mutex_);

    const int64_t now = currentUnixMillis();
    robotops::ticket_diagnosis::BugTicket ticket;
    ticket.set_bug_id(makeId("bug", ++bug_sequence_));
    ticket.set_title(request.title());
    ticket.set_description(request.description());
    ticket.set_robot_type(request.robot_type());
    ticket.set_robot_sn(request.robot_sn());
    ticket.set_main_module(request.main_module());
    ticket.set_occurred_time(request.occurred_time());
    ticket.set_software_version(request.software_version());
    ticket.set_branch(request.branch());
    ticket.set_commit(request.commit());
    ticket.set_log_package_id(request.log_package_id());
    ticket.set_source_repo(request.source_repo());
    ticket.set_assigned_to(request.assigned_to());
    ticket.set_status("OPEN");
    ticket.set_created_at(now);
    ticket.set_updated_at(now);

    tickets_[ticket.bug_id()] = ticket;
    ticket_order_.push_back(ticket.bug_id());
    return ticket;
}

std::optional<robotops::ticket_diagnosis::BugTicket> TicketDiagnosisStore::getTicket(
    const std::string& bug_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto it = tickets_.find(bug_id);
    if (it == tickets_.end()) {
        return std::nullopt;
    }
    return it->second;
}

std::vector<robotops::ticket_diagnosis::BugTicket> TicketDiagnosisStore::listTickets(
    const TicketListFilter& filter,
    int64_t* total) const {
    std::vector<robotops::ticket_diagnosis::BugTicket> matched;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto it = ticket_order_.rbegin(); it != ticket_order_.rend(); ++it) {
            const auto ticket_it = tickets_.find(*it);
            if (ticket_it != tickets_.end() && ticketMatches(ticket_it->second, filter)) {
                matched.push_back(ticket_it->second);
            }
        }
    }

    if (total != nullptr) {
        *total = static_cast<int64_t>(matched.size());
    }

    const int page = normalizePage(filter.page);
    const int page_size = normalizePageSize(filter.page_size);
    const size_t begin = static_cast<size_t>((page - 1) * page_size);
    if (begin >= matched.size()) {
        return {};
    }
    const size_t end = std::min(matched.size(), begin + static_cast<size_t>(page_size));
    return std::vector<robotops::ticket_diagnosis::BugTicket>(
        matched.begin() + static_cast<std::ptrdiff_t>(begin),
        matched.begin() + static_cast<std::ptrdiff_t>(end));
}

robotops::ticket_diagnosis::DiagnosisTask TicketDiagnosisStore::createDiagnosisTask(
    const std::string& bug_id,
    const std::string& agent_request_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    const int64_t now = currentUnixMillis();
    robotops::ticket_diagnosis::DiagnosisTask task;
    task.set_task_id(makeId("diag-task", ++task_sequence_));
    task.set_bug_id(bug_id);
    task.set_status(robotops::common::TASK_STATUS_PENDING);
    task.set_agent_request_id(agent_request_id);
    task.set_message("diagnosis task created; agent-service call is reserved");
    task.set_created_at(now);
    task.set_updated_at(now);

    tasks_[task.task_id()] = task;
    task_order_.push_back(task.task_id());
    return task;
}

std::optional<robotops::ticket_diagnosis::DiagnosisTask> TicketDiagnosisStore::getDiagnosisTask(
    const std::string& task_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto it = tasks_.find(task_id);
    if (it == tasks_.end()) {
        return std::nullopt;
    }
    return it->second;
}

robotops::ticket_diagnosis::DiagnosisReport TicketDiagnosisStore::saveReport(
    const robotops::ticket_diagnosis::DiagnosisReport& request_report) {
    std::lock_guard<std::mutex> lock(mutex_);

    const int64_t now = currentUnixMillis();
    robotops::ticket_diagnosis::DiagnosisReport report = request_report;
    if (report.report_id().empty()) {
        report.set_report_id(makeId("diag-report", ++report_sequence_));
        report_order_.push_back(report.report_id());
    } else if (reports_.find(report.report_id()) == reports_.end()) {
        report_order_.push_back(report.report_id());
    }
    if (report.status() == robotops::common::TASK_STATUS_UNSPECIFIED) {
        report.set_status(robotops::common::TASK_STATUS_SUCCEEDED);
    }
    if (report.created_at() <= 0) {
        report.set_created_at(now);
    }
    report.set_updated_at(now);

    reports_[report.report_id()] = report;

    const auto task_it = tasks_.find(report.task_id());
    if (task_it != tasks_.end()) {
        task_it->second.set_status(report.status());
        task_it->second.set_message("diagnosis report saved");
        task_it->second.set_updated_at(now);
    }

    return report;
}

std::optional<robotops::ticket_diagnosis::DiagnosisReport> TicketDiagnosisStore::getReport(
    const std::string& report_id,
    const std::string& task_id,
    const std::string& bug_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!report_id.empty()) {
        const auto it = reports_.find(report_id);
        if (it == reports_.end()) {
            return std::nullopt;
        }
        return it->second;
    }

    for (auto it = report_order_.rbegin(); it != report_order_.rend(); ++it) {
        const auto report_it = reports_.find(*it);
        if (report_it == reports_.end()) {
            continue;
        }
        const auto& report = report_it->second;
        if (!task_id.empty() && report.task_id() != task_id) {
            continue;
        }
        if (!bug_id.empty() && report.bug_id() != bug_id) {
            continue;
        }
        return report;
    }

    return std::nullopt;
}

std::string TicketDiagnosisStore::makeId(const std::string& prefix, int64_t sequence) {
    std::ostringstream oss;
    oss << prefix << "-" << std::setw(6) << std::setfill('0') << sequence;
    return oss.str();
}

int64_t TicketDiagnosisStore::currentUnixMillis() {
    const auto now = std::chrono::system_clock::now().time_since_epoch();
    return std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
}

bool TicketDiagnosisStore::ticketMatches(
    const robotops::ticket_diagnosis::BugTicket& ticket,
    const TicketListFilter& filter) {
    if (filter.robot_type != robotops::common::ROBOT_TYPE_UNSPECIFIED
        && ticket.robot_type() != filter.robot_type) {
        return false;
    }
    if (!filter.main_module.empty() && ticket.main_module() != filter.main_module) {
        return false;
    }
    if (!filter.status.empty() && ticket.status() != filter.status) {
        return false;
    }
    if (!filter.keyword.empty()
        && !containsCaseInsensitive(ticket.title(), filter.keyword)
        && !containsCaseInsensitive(ticket.description(), filter.keyword)
        && !containsCaseInsensitive(ticket.bug_id(), filter.keyword)
        && !containsCaseInsensitive(ticket.log_package_id(), filter.keyword)) {
        return false;
    }
    return true;
}

bool TicketDiagnosisStore::containsCaseInsensitive(const std::string& value, const std::string& keyword) {
    auto lower = [](std::string text) {
        std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        return text;
    };
    return lower(value).find(lower(keyword)) != std::string::npos;
}

int TicketDiagnosisStore::normalizePage(int page) {
    return page <= 0 ? 1 : page;
}

int TicketDiagnosisStore::normalizePageSize(int page_size) {
    if (page_size <= 0) {
        return 20;
    }
    return page_size > 200 ? 200 : page_size;
}

} // namespace robotops::ticket_diagnosis_service
