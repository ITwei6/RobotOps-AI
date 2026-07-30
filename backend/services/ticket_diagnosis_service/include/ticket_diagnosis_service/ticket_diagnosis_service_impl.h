#pragma once

#include "ticket_diagnosis.pb.h"
#include "ticket_diagnosis_service/agent_client.h"
#include "ticket_diagnosis_service/ticket_diagnosis_store.h"

namespace robotops::ticket_diagnosis_service {

class TicketDiagnosisServiceImpl : public robotops::ticket_diagnosis::TicketDiagnosisService {
public:
    TicketDiagnosisServiceImpl(TicketDiagnosisStore* store, AgentClient* agent_client);

    void CreateBugTicket(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::CreateBugTicketRequest* request,
        robotops::ticket_diagnosis::CreateBugTicketResponse* response,
        ::google::protobuf::Closure* done) override;

    void GetBugTicket(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::GetBugTicketRequest* request,
        robotops::ticket_diagnosis::GetBugTicketResponse* response,
        ::google::protobuf::Closure* done) override;

    void ListBugTickets(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::ListBugTicketsRequest* request,
        robotops::ticket_diagnosis::ListBugTicketsResponse* response,
        ::google::protobuf::Closure* done) override;

    void CreateDiagnosisTask(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::CreateDiagnosisTaskRequest* request,
        robotops::ticket_diagnosis::CreateDiagnosisTaskResponse* response,
        ::google::protobuf::Closure* done) override;

    void GetDiagnosisTask(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::GetDiagnosisTaskRequest* request,
        robotops::ticket_diagnosis::GetDiagnosisTaskResponse* response,
        ::google::protobuf::Closure* done) override;

    void SaveDiagnosisReport(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::SaveDiagnosisReportRequest* request,
        robotops::ticket_diagnosis::SaveDiagnosisReportResponse* response,
        ::google::protobuf::Closure* done) override;

    void GetDiagnosisReport(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::GetDiagnosisReportRequest* request,
        robotops::ticket_diagnosis::GetDiagnosisReportResponse* response,
        ::google::protobuf::Closure* done) override;

    void RunDiagnosis(::google::protobuf::RpcController* controller,
        const robotops::ticket_diagnosis::RunDiagnosisRequest* request,
        robotops::ticket_diagnosis::RunDiagnosisResponse* response,
        ::google::protobuf::Closure* done) override;

private:
    TicketDiagnosisStore* store_;
    AgentClient* agent_client_;
};

} // namespace robotops::ticket_diagnosis_service
