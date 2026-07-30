#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <string>
#include <thread>

#include "log.h"
#include "rpc.h"
#include "ticket_diagnosis_service/ticket_diagnosis_service_impl.h"
#include "ticket_diagnosis_service/ticket_diagnosis_store.h"

namespace {

std::atomic_bool g_stop{false};

void handleSignal(int) {
    g_stop.store(true);
}

int getenvIntOrDefault(const char* name, int fallback) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return fallback;
    }
    try {
        return std::stoi(value);
    } catch (...) {
        return fallback;
    }
}

} // namespace

int main() {
    tewlog::tewlog_init();
    std::signal(SIGINT, handleSignal);
    std::signal(SIGTERM, handleSignal);

    robotops::ticket_diagnosis_service::TicketDiagnosisStore store;

    const int port = getenvIntOrDefault("ROBOTOPS_TICKET_DIAGNOSIS_RPC_PORT", 9502);
    auto server = tewrpc::RpcServerFactory::create(
        port,
        new robotops::ticket_diagnosis_service::TicketDiagnosisServiceImpl(&store));

    INF("robotops ticket-diagnosis-service started: rpc_port={}", port);
    while (!g_stop.load()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    server->Stop(0);
    server->Join();
    return 0;
}
