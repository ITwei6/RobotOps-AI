#include "log_service/log_service_impl.h"

#include <brpc/server.h>

#include <exception>
#include <vector>

namespace robotops::log_service {
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

} // namespace

LogServiceImpl::LogServiceImpl(LogParser* parser, LogIndex* index)
    : parser_(parser),
      index_(index) {
}

void LogServiceImpl::ImportLogPackage(::google::protobuf::RpcController* controller,
    const robotops::log::ImportLogPackageRequest* request,
    robotops::log::ImportLogPackageResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->package_path().empty()) {
        setResponse(response->mutable_response(), 400, "package_path is required");
        return;
    }
    if (request->package_id().empty()) {
        setResponse(response->mutable_response(), 400, "package_id is required");
        return;
    }

    try {
        const auto parsed = parser_->parsePackage(
            request->bug_id(),
            request->package_id(),
            request->package_path(),
            request->robot_type(),
            request->robot_sn());

        std::vector<robotops::log::LogFileInfo> files;
        std::vector<robotops::log::ModuleLogEntry> logs;
        for (const auto& item : parsed) {
            files.push_back(item.file);
            *response->add_files() = item.file;
            logs.insert(logs.end(), item.logs.begin(), item.logs.end());
        }

        index_->append(files, logs);

        setResponse(response->mutable_response(), 0, "ok");
        response->set_package_id(request->package_id());
        response->set_file_count(static_cast<int32_t>(files.size()));
        response->set_log_count(static_cast<int32_t>(logs.size()));
    } catch (const std::exception& e) {
        setResponse(response->mutable_response(), 500, e.what());
    }
}

void LogServiceImpl::QueryLogs(::google::protobuf::RpcController* controller,
    const robotops::log::QueryLogsRequest* request,
    robotops::log::QueryLogsResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    LogQueryFilter filter;
    filter.page = pageOrDefault(request->page());
    filter.page_size = pageSizeOrDefault(request->page());
    filter.bug_id = request->bug_id();
    filter.package_id = request->package_id();
    filter.module_name = request->module_name();
    filter.log_level = request->log_level();
    filter.keyword = request->keyword();
    filter.start_time = request->time_range().start_time();
    filter.end_time = request->time_range().end_time();

    int64_t total = 0;
    const auto logs = index_->query(filter, &total);

    setResponse(response->mutable_response(), 0, "ok");
    response->mutable_page()->set_page(filter.page);
    response->mutable_page()->set_page_size(filter.page_size);
    response->mutable_page()->set_total(total);
    for (const auto& log : logs) {
        *response->add_logs() = log;
    }
}

void LogServiceImpl::GetLogContext(::google::protobuf::RpcController* controller,
    const robotops::log::GetLogContextRequest* request,
    robotops::log::GetLogContextResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    if (request->center_time() <= 0) {
        setResponse(response->mutable_response(), 400, "center_time is required");
        return;
    }

    const auto logs = index_->context(
        request->bug_id(),
        request->package_id(),
        request->module_name(),
        request->center_time(),
        request->before_ms(),
        request->after_ms(),
        request->limit());

    setResponse(response->mutable_response(), 0, "ok");
    for (const auto& log : logs) {
        *response->add_logs() = log;
    }
}

void LogServiceImpl::ListLogFiles(::google::protobuf::RpcController* controller,
    const robotops::log::ListLogFilesRequest* request,
    robotops::log::ListLogFilesResponse* response,
    ::google::protobuf::Closure* done) {
    (void)controller;
    brpc::ClosureGuard done_guard(done);

    const auto files = index_->listFiles(request->package_id(), request->module_name());
    setResponse(response->mutable_response(), 0, "ok");
    for (const auto& file : files) {
        *response->add_files() = file;
    }
}

} // namespace robotops::log_service
