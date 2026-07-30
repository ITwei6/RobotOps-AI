#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <string>
#include <thread>

#include "log.h"
#include "log_service/log_index.h"
#include "log_service/log_parser.h"
#include "log_service/log_service_impl.h"
#include "rpc.h"

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

    robotops::log_service::LogParser parser;
    robotops::log_service::LogIndex index;

    const int port = getenvIntOrDefault("ROBOTOPS_LOG_RPC_PORT", 9501);
    auto server = tewrpc::RpcServerFactory::create(
        port,
        new robotops::log_service::LogServiceImpl(&parser, &index));

    INF("robotops log-service started: rpc_port={}", port);
    while (!g_stop.load()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    server->Stop(0);
    server->Join();
    return 0;
}

