#include "log_service/log_index.h"

#include <algorithm>

namespace robotops::log_service {
namespace {

bool inTimeRange(int64_t timestamp, int64_t start_time, int64_t end_time) {
    if (start_time > 0 && timestamp < start_time) {
        return false;
    }
    if (end_time > 0 && timestamp > end_time) {
        return false;
    }
    return true;
}

} // namespace

void LogIndex::append(const std::vector<robotops::log::LogFileInfo>& files,
    const std::vector<robotops::log::ModuleLogEntry>& logs) {
    std::lock_guard<std::mutex> lock(mutex_);
    files_.insert(files_.end(), files.begin(), files.end());
    logs_.insert(logs_.end(), logs.begin(), logs.end());
}

std::vector<robotops::log::ModuleLogEntry> LogIndex::query(const LogQueryFilter& filter, int64_t* total) const {
    std::vector<robotops::log::ModuleLogEntry> matched;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        for (const auto& log : logs_) {
            if (matches(log, filter)) {
                matched.push_back(log);
            }
        }
    }

    std::sort(matched.begin(), matched.end(), [](const auto& lhs, const auto& rhs) {
        if (lhs.log_time() == rhs.log_time()) {
            return lhs.line_no() < rhs.line_no();
        }
        return lhs.log_time() < rhs.log_time();
    });

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
    return std::vector<robotops::log::ModuleLogEntry>(matched.begin() + static_cast<std::ptrdiff_t>(begin),
        matched.begin() + static_cast<std::ptrdiff_t>(end));
}

std::vector<robotops::log::ModuleLogEntry> LogIndex::context(
    const std::string& bug_id,
    const std::string& package_id,
    const std::string& module_name,
    int64_t center_time,
    int64_t before_ms,
    int64_t after_ms,
    int limit) const {
    LogQueryFilter filter;
    filter.bug_id = bug_id;
    filter.package_id = package_id;
    filter.module_name = module_name;
    filter.start_time = center_time - std::max<int64_t>(before_ms, 0);
    filter.end_time = center_time + std::max<int64_t>(after_ms, 0);
    filter.page = 1;
    filter.page_size = limit <= 0 ? 50 : std::min(limit, 200);

    int64_t total = 0;
    return query(filter, &total);
}

std::vector<robotops::log::LogFileInfo> LogIndex::listFiles(const std::string& package_id, const std::string& module_name) const {
    std::vector<robotops::log::LogFileInfo> result;
    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto& file : files_) {
        if (!package_id.empty() && file.package_id() != package_id) {
            continue;
        }
        if (!module_name.empty() && file.module_name() != module_name) {
            continue;
        }
        result.push_back(file);
    }
    return result;
}

bool LogIndex::matches(const robotops::log::ModuleLogEntry& log, const LogQueryFilter& filter) {
    if (!filter.bug_id.empty() && log.bug_id() != filter.bug_id) {
        return false;
    }
    if (!filter.package_id.empty() && log.package_id() != filter.package_id) {
        return false;
    }
    if (!filter.module_name.empty() && log.module_name() != filter.module_name) {
        return false;
    }
    if (!filter.log_level.empty() && log.log_level() != filter.log_level) {
        return false;
    }
    if (!inTimeRange(log.log_time(), filter.start_time, filter.end_time)) {
        return false;
    }
    if (!filter.keyword.empty()
        && !contains(log.message(), filter.keyword)
        && !contains(log.raw_line(), filter.keyword)
        && !contains(log.trace_id(), filter.keyword)
        && !contains(log.task_id(), filter.keyword)
        && !contains(log.session_id(), filter.keyword)) {
        return false;
    }
    return true;
}

bool LogIndex::contains(const std::string& value, const std::string& keyword) {
    return keyword.empty() || value.find(keyword) != std::string::npos;
}

int LogIndex::normalizePage(int page) {
    return page <= 0 ? 1 : page;
}

int LogIndex::normalizePageSize(int page_size) {
    if (page_size <= 0) {
        return 20;
    }
    return page_size > 200 ? 200 : page_size;
}

} // namespace robotops::log_service

