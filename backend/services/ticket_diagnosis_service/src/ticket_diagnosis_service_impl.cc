#include "ticket_diagnosis_service/ticket_diagnosis_service_impl.h"

#include <brpc/server.h>

namespace robotops::ticket_diagnosis_service {
namespace {

void setResponse(robotops::common::CommonResponse* response, int code, const std::string& message) {
    response->set_code(code);
    response->set_message(message);
}

int pageOrDefault(const robotops::common::PageRequest& page) {
    return page.page() <= 0 ? 1 : page.page();
}

int pageSizeOrDefault(const robotops::common::PageRequest& page) {
    if (page.page_size() <= 0) {
        return 20;
    }
    return page.page_size() > 200 ? 200 : page.page_size();
}

bool isValidRobotType(robotops::common::RobotType robot_type) {
    return robot_type == robotops::common::ROBOT_TYPE_T
        || robot_type == robotops::common::ROBOT_TYPE_Q;
}

} // namespace

TicketDiagnosisServiceImpl::TicketDiagnosisServiceImpl(TicketDiagnosisStore* store, AgentClient* agent_client)
    : store_(store),
      agent_client_(agent_client) {
}

void TicketDiagnosisServiceImpl::CreateBugTicket(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::CreateBugTicketRequest* request,
    robotops::ticket_diagnosis::CreateBugTicketResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->title().empty()) {
        setResponse(response->mutable_response(), 400, "title is required");
        return;
    }
    if (request->description().empty()) {
        setResponse(response->mutable_response(), 400, "description is required");
        return;
    }
    if (!isValidRobotType(request->robot_type())) {
        setResponse(response->mutable_response(), 400, "robot_type must be ROBOT_TYPE_T or ROBOT_TYPE_Q");
        return;
    }
    if (request->main_module().empty()) {
        setResponse(response->mutable_response(), 400, "main_module is required");
        return;
    }
    if (request->occurred_time() <= 0) {
        setResponse(response->mutable_response(), 400, "occurred_time is required");
        return;
    }

    *response->mutable_ticket() = store_->createTicket(*request);
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::GetBugTicket(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::GetBugTicketRequest* request,
    robotops::ticket_diagnosis::GetBugTicketResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->bug_id().empty()) {
        setResponse(response->mutable_response(), 400, "bug_id is required");
        return;
    }

    const auto ticket = store_->getTicket(request->bug_id());
    if (!ticket.has_value()) {
        setResponse(response->mutable_response(), 404, "bug ticket not found");
        return;
    }

    *response->mutable_ticket() = ticket.value();
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::ListBugTickets(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::ListBugTicketsRequest* request,
    robotops::ticket_diagnosis::ListBugTicketsResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    TicketListFilter filter;
    filter.page = pageOrDefault(request->page());
    filter.page_size = pageSizeOrDefault(request->page());
    filter.robot_type = request->robot_type();
    filter.main_module = request->main_module();
    filter.status = request->status();
    filter.keyword = request->keyword();

    int64_t total = 0;
    const auto tickets = store_->listTickets(filter, &total);

    response->mutable_page()->set_page(filter.page);
    response->mutable_page()->set_page_size(filter.page_size);
    response->mutable_page()->set_total(total);
    for (const auto& ticket : tickets) {
        *response->add_tickets() = ticket;
    }
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::CreateDiagnosisTask(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::CreateDiagnosisTaskRequest* request,
    robotops::ticket_diagnosis::CreateDiagnosisTaskResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->bug_id().empty()) {
        setResponse(response->mutable_response(), 400, "bug_id is required");
        return;
    }
    if (!store_->getTicket(request->bug_id()).has_value()) {
        setResponse(response->mutable_response(), 404, "bug ticket not found");
        return;
    }

    *response->mutable_task() = store_->createDiagnosisTask(request->bug_id(), request->agent_request_id());
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::GetDiagnosisTask(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::GetDiagnosisTaskRequest* request,
    robotops::ticket_diagnosis::GetDiagnosisTaskResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->task_id().empty()) {
        setResponse(response->mutable_response(), 400, "task_id is required");
        return;
    }

    const auto task = store_->getDiagnosisTask(request->task_id());
    if (!task.has_value()) {
        setResponse(response->mutable_response(), 404, "diagnosis task not found");
        return;
    }

    *response->mutable_task() = task.value();
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::SaveDiagnosisReport(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::SaveDiagnosisReportRequest* request,
    robotops::ticket_diagnosis::SaveDiagnosisReportResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    const auto& report = request->report();
    if (report.bug_id().empty()) {
        setResponse(response->mutable_response(), 400, "report.bug_id is required");
        return;
    }
    if (!store_->getTicket(report.bug_id()).has_value()) {
        setResponse(response->mutable_response(), 404, "bug ticket not found");
        return;
    }
    if (!report.task_id().empty() && !store_->getDiagnosisTask(report.task_id()).has_value()) {
        setResponse(response->mutable_response(), 404, "diagnosis task not found");
        return;
    }

    *response->mutable_report() = store_->saveReport(report);
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::GetDiagnosisReport(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::GetDiagnosisReportRequest* request,
    robotops::ticket_diagnosis::GetDiagnosisReportResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->report_id().empty() && request->task_id().empty() && request->bug_id().empty()) {
        setResponse(response->mutable_response(), 400, "report_id, task_id or bug_id is required");
        return;
    }

    const auto report = store_->getReport(request->report_id(), request->task_id(), request->bug_id());
    if (!report.has_value()) {
        setResponse(response->mutable_response(), 404, "diagnosis report not found");
        return;
    }

    *response->mutable_report() = report.value();
    setResponse(response->mutable_response(), 0, "ok");
}

void TicketDiagnosisServiceImpl::RunDiagnosis(::google::protobuf::RpcController* controller,
    const robotops::ticket_diagnosis::RunDiagnosisRequest* request,
    robotops::ticket_diagnosis::RunDiagnosisResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->bug_id().empty()) {
        setResponse(response->mutable_response(), 400, "bug_id is required");
        return;
    }

    const auto ticket = store_->getTicket(request->bug_id());
    if (!ticket.has_value()) {
        setResponse(response->mutable_response(), 404, "bug ticket not found");
        return;
    }

    auto task = store_->createDiagnosisTask(request->bug_id(), "agent-service");
    *response->mutable_task() = task;

    const auto agent_result = agent_client_->diagnose(ticket.value(), task, *request);
    if (!agent_result.ok) {
        const std::string message = "agent-service diagnose failed: " + agent_result.message;
        const auto failed_task = store_->updateDiagnosisTask(
            task.task_id(),
            robotops::common::TASK_STATUS_FAILED,
            message);
        if (failed_task.has_value()) {
            *response->mutable_task() = failed_task.value();
        }
        setResponse(response->mutable_response(), 502, message);
        return;
    }

    const auto report = store_->saveReport(agent_result.report);
    *response->mutable_report() = report;
    const auto updated_task = store_->getDiagnosisTask(task.task_id());
    if (updated_task.has_value()) {
        *response->mutable_task() = updated_task.value();
    }
    setResponse(response->mutable_response(), 0, "ok");
}

} // namespace robotops::ticket_diagnosis_service
