#include "ticket_diagnosis_service/agent_client.h"

#include <cpr/cpr.h>
#include <json/json.h>

#include <sstream>
#include <utility>

namespace robotops::ticket_diagnosis_service {
namespace {

std::string robotTypeToString(robotops::common::RobotType robot_type) {
    switch (robot_type) {
        case robotops::common::ROBOT_TYPE_T:
            return "ROBOT_TYPE_T";
        case robotops::common::ROBOT_TYPE_Q:
            return "ROBOT_TYPE_Q";
        default:
            return "ROBOT_TYPE_UNSPECIFIED";
    }
}

robotops::common::TaskStatus taskStatusFromString(const std::string& status) {
    if (status == "TASK_STATUS_PENDING") {
        return robotops::common::TASK_STATUS_PENDING;
    }
    if (status == "TASK_STATUS_RUNNING") {
        return robotops::common::TASK_STATUS_RUNNING;
    }
    if (status == "TASK_STATUS_FAILED") {
        return robotops::common::TASK_STATUS_FAILED;
    }
    return robotops::common::TASK_STATUS_SUCCEEDED;
}

Json::Value logToJson(const robotops::ticket_diagnosis::DiagnosisLogEvidence& log) {
    Json::Value value(Json::objectValue);
    value["module_name"] = log.module_name();
    value["file_name"] = log.file_name();
    value["line_no"] = log.line_no();
    value["log_time"] = Json::Int64(log.log_time());
    value["log_level"] = log.log_level();
    value["message"] = log.message();
    value["raw_line"] = log.raw_line();
    return value;
}

Json::Value sourceToJson(const robotops::ticket_diagnosis::DiagnosisSourceEvidence& source) {
    Json::Value value(Json::objectValue);
    value["repo"] = source.repo();
    value["branch"] = source.branch();
    value["commit"] = source.commit();
    value["file_path"] = source.file_path();
    value["function_name"] = source.function_name();
    value["matched_text"] = source.matched_text();
    value["snippet"] = source.snippet();
    return value;
}

Json::Value buildRequestJson(
    const robotops::ticket_diagnosis::BugTicket& ticket,
    const robotops::ticket_diagnosis::RunDiagnosisRequest& request) {
    Json::Value root(Json::objectValue);
    Json::Value bug(Json::objectValue);
    bug["bug_id"] = ticket.bug_id();
    bug["title"] = ticket.title();
    bug["description"] = ticket.description();
    bug["robot_type"] = robotTypeToString(ticket.robot_type());
    bug["main_module"] = ticket.main_module();
    bug["occurred_time"] = Json::Int64(ticket.occurred_time());
    bug["software_version"] = ticket.software_version();
    bug["branch"] = ticket.branch();
    bug["commit"] = ticket.commit();
    bug["log_package_id"] = request.log_package_id().empty()
        ? ticket.log_package_id()
        : request.log_package_id();
    bug["source_repo"] = ticket.source_repo();
    root["bug"] = bug;

    root["logs"] = Json::arrayValue;
    for (const auto& log : request.logs()) {
        root["logs"].append(logToJson(log));
    }

    root["sources"] = Json::arrayValue;
    for (const auto& source : request.sources()) {
        root["sources"].append(sourceToJson(source));
    }

    root["history_cases"] = Json::arrayValue;
    root["knowledge"] = Json::arrayValue;
    return root;
}

std::string writeJson(const Json::Value& value) {
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "";
    return Json::writeString(builder, value);
}

bool readJson(const std::string& text, Json::Value* value, std::string* error) {
    Json::CharReaderBuilder builder;
    std::istringstream input(text);
    return Json::parseFromStream(builder, input, value, error);
}

void fillLogEvidence(const Json::Value& value, robotops::ticket_diagnosis::DiagnosisLogEvidence* log) {
    log->set_module_name(value.get("module_name", "").asString());
    log->set_file_name(value.get("file_name", "").asString());
    log->set_line_no(value.get("line_no", 0).asInt());
    log->set_log_time(value.get("log_time", Json::Int64(0)).asInt64());
    log->set_log_level(value.get("log_level", "").asString());
    log->set_message(value.get("message", "").asString());
    log->set_raw_line(value.get("raw_line", "").asString());
}

void fillSourceEvidence(const Json::Value& value, robotops::ticket_diagnosis::DiagnosisSourceEvidence* source) {
    source->set_repo(value.get("repo", "").asString());
    source->set_branch(value.get("branch", "").asString());
    source->set_commit(value.get("commit", "").asString());
    source->set_file_path(value.get("file_path", "").asString());
    source->set_function_name(value.get("function_name", "").asString());
    source->set_matched_text(value.get("matched_text", "").asString());
    source->set_snippet(value.get("snippet", "").asString());
}

robotops::ticket_diagnosis::DiagnosisReport reportFromJson(
    const Json::Value& value,
    const robotops::ticket_diagnosis::BugTicket& ticket,
    const robotops::ticket_diagnosis::DiagnosisTask& task) {
    robotops::ticket_diagnosis::DiagnosisReport report;
    report.set_task_id(task.task_id());
    report.set_bug_id(ticket.bug_id());
    report.set_status(taskStatusFromString(value.get("status", "TASK_STATUS_SUCCEEDED").asString()));
    report.set_suspected_module(value.get("suspected_module", ticket.main_module()).asString());
    report.set_summary(value.get("summary", "").asString());
    report.set_confidence(value.get("confidence", 0.0).asDouble());

    for (const auto& cause : value["possible_causes"]) {
        report.add_possible_causes(cause.asString());
    }
    for (const auto& action : value["recommended_actions"]) {
        report.add_recommended_actions(action.asString());
    }
    for (const auto& question : value["questions_for_human"]) {
        report.add_questions_for_human(question.asString());
    }
    for (const auto& log_value : value["evidence_logs"]) {
        fillLogEvidence(log_value, report.add_evidence_logs());
    }
    for (const auto& source_value : value["evidence_sources"]) {
        fillSourceEvidence(source_value, report.add_evidence_sources());
    }
    return report;
}

} // namespace

AgentClient::AgentClient(std::string default_endpoint, int timeout_ms)
    : default_endpoint_(std::move(default_endpoint)),
      timeout_ms_(std::max(timeout_ms, 1000)) {
}

AgentDiagnosisResult AgentClient::diagnose(
    const robotops::ticket_diagnosis::BugTicket& ticket,
    const robotops::ticket_diagnosis::DiagnosisTask& task,
    const robotops::ticket_diagnosis::RunDiagnosisRequest& request) const {
    AgentDiagnosisResult result;

    const std::string endpoint = endpointOrDefault(request.agent_endpoint());
    if (endpoint.empty()) {
        result.message = "agent endpoint is empty";
        return result;
    }

    const auto payload = writeJson(buildRequestJson(ticket, request));
    const auto response = cpr::Post(
        cpr::Url{endpoint + "/diagnose"},
        cpr::Header{{"Content-Type", "application/json"}},
        cpr::Body{payload},
        cpr::Timeout{timeout_ms_});

    result.http_status = static_cast<int>(response.status_code);
    if (response.error) {
        result.message = response.error.message;
        return result;
    }
    if (response.status_code < 200 || response.status_code >= 300) {
        result.message = "agent-service returned http status " + std::to_string(response.status_code);
        if (!response.text.empty()) {
            result.message += ": " + response.text.substr(0, 512);
        }
        return result;
    }

    Json::Value body;
    std::string parse_error;
    if (!readJson(response.text, &body, &parse_error)) {
        result.message = "failed to parse agent-service response: " + parse_error;
        return result;
    }

    result.report = reportFromJson(body, ticket, task);
    result.ok = true;
    result.message = "ok";
    return result;
}

std::string AgentClient::endpointOrDefault(const std::string& endpoint) const {
    std::string value = endpoint.empty() ? default_endpoint_ : endpoint;
    while (!value.empty() && value.back() == '/') {
        value.pop_back();
    }
    return value;
}

} // namespace robotops::ticket_diagnosis_service
