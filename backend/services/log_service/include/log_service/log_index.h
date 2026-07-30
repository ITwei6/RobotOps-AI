#pragma once

#include <mutex>
#include <string>
#include <vector>

#include "log.pb.h"

namespace robotops::log_service {

struct LogQueryFilter {
    int page = 1;
    int page_size = 20;
    std::string bug_id;
    std::string package_id;
    std::string module_name;
    std::string log_level;
    std::string keyword;
    int64_t start_time = 0;
    int64_t end_time = 0;
};

class LogIndex {
public:
    void append(const std::vector<robotops::log::LogFileInfo>& files,
        const std::vector<robotops::log::ModuleLogEntry>& logs);

    std::vector<robotops::log::ModuleLogEntry> query(const LogQueryFilter& filter, int64_t* total) const;
    std::vector<robotops::log::ModuleLogEntry> context(
        const std::string& bug_id,
        const std::string& package_id,
        const std::string& module_name,
        int64_t center_time,
        int64_t before_ms,
        int64_t after_ms,
        int limit) const;
    std::vector<robotops::log::LogFileInfo> listFiles(const std::string& package_id, const std::string& module_name) const;

private:
    static bool matches(const robotops::log::ModuleLogEntry& log, const LogQueryFilter& filter);
    static bool contains(const std::string& value, const std::string& keyword);
    static int normalizePage(int page);
    static int normalizePageSize(int page_size);

private:
    mutable std::mutex mutex_;
    std::vector<robotops::log::LogFileInfo> files_;
    std::vector<robotops::log::ModuleLogEntry> logs_;
};

} // namespace robotops::log_service

