#pragma once

#include "log.pb.h"
#include "log_service/log_index.h"
#include "log_service/log_parser.h"

namespace robotops::log_service {

class LogServiceImpl : public robotops::log::LogService {
public:
    LogServiceImpl(LogParser* parser, LogIndex* index);

    void ImportLogPackage(::google::protobuf::RpcController* controller,
        const robotops::log::ImportLogPackageRequest* request,
        robotops::log::ImportLogPackageResponse* response,
        ::google::protobuf::Closure* done) override;

    void QueryLogs(::google::protobuf::RpcController* controller,
        const robotops::log::QueryLogsRequest* request,
        robotops::log::QueryLogsResponse* response,
        ::google::protobuf::Closure* done) override;

    void GetLogContext(::google::protobuf::RpcController* controller,
        const robotops::log::GetLogContextRequest* request,
        robotops::log::GetLogContextResponse* response,
        ::google::protobuf::Closure* done) override;

    void ListLogFiles(::google::protobuf::RpcController* controller,
        const robotops::log::ListLogFilesRequest* request,
        robotops::log::ListLogFilesResponse* response,
        ::google::protobuf::Closure* done) override;

private:
    LogParser* parser_;
    LogIndex* index_;
};

} // namespace robotops::log_service

