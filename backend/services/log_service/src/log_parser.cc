#include "log_service/log_parser.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <regex>
#include <sstream>
#include <stdexcept>

namespace robotops::log_service {
namespace {

int64_t currentUnixMillis() {
    const auto now = std::chrono::system_clock::now().time_since_epoch();
    return std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
}

std::string toLower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

std::time_t toLocalTimeT(std::tm* tm) {
    tm->tm_isdst = -1;
    return std::mktime(tm);
}

} // namespace

std::vector<ParsedLogFile> LogParser::parsePackage(
    const std::string& bug_id,
    const std::string& package_id,
    const std::string& package_path,
    robotops::common::RobotType robot_type,
    const std::string& robot_sn) const {
    if (package_path.empty()) {
        throw std::invalid_argument("package_path is required");
    }

    const std::filesystem::path root(package_path);
    if (!std::filesystem::exists(root)) {
        throw std::invalid_argument("package_path does not exist: " + package_path);
    }
    if (!std::filesystem::is_directory(root)) {
        throw std::invalid_argument("package_path must be an extracted log directory in MVP");
    }

    std::vector<ParsedLogFile> parsed;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(root)) {
        if (!entry.is_regular_file() || !isLogFile(entry.path())) {
            continue;
        }
        parsed.push_back(parseFile(root, entry.path(), bug_id, package_id, robot_type, robot_sn));
    }

    std::sort(parsed.begin(), parsed.end(), [](const auto& lhs, const auto& rhs) {
        if (lhs.file.module_name() == rhs.file.module_name()) {
            return lhs.file.file_name() < rhs.file.file_name();
        }
        return lhs.file.module_name() < rhs.file.module_name();
    });
    return parsed;
}

ParsedLogFile LogParser::parseFile(
    const std::filesystem::path& root,
    const std::filesystem::path& file_path,
    const std::string& bug_id,
    const std::string& package_id,
    robotops::common::RobotType robot_type,
    const std::string& robot_sn) const {
    const std::string module_name = moduleNameFromPath(root, file_path);
    ParsedLogFile result;
    result.file.set_package_id(package_id);
    result.file.set_module_name(module_name);
    result.file.set_file_name(file_path.filename().string());
    result.file.set_file_path(file_path.string());

    std::ifstream input(file_path);
    if (!input.is_open()) {
        return result;
    }

    std::string line;
    int line_no = 0;
    while (std::getline(input, line)) {
        ++line_no;
        if (line.empty()) {
            continue;
        }

        auto* log = &result.logs.emplace_back();
        log->set_log_id(makeLogId(package_id, module_name, line_no));
        log->set_bug_id(bug_id);
        log->set_package_id(package_id);
        log->set_robot_sn(robot_sn);
        log->set_robot_type(robot_type);
        log->set_module_name(module_name);
        log->set_file_name(file_path.filename().string());
        log->set_line_no(line_no);
        log->set_log_time(parseTimestampMillis(line));
        log->set_log_level(parseLevel(line));
        log->set_message(parseMessage(line));
        log->set_raw_line(line);
    }

    result.file.set_line_count(line_no);
    return result;
}

std::string LogParser::moduleNameFromPath(const std::filesystem::path& root, const std::filesystem::path& file_path) {
    const auto relative = std::filesystem::relative(file_path, root);
    if (relative.empty()) {
        return "unknown";
    }
    const auto first = relative.begin();
    if (first == relative.end()) {
        return "unknown";
    }
    const std::string module = first->string();
    return module.empty() ? "unknown" : module;
}

bool LogParser::isLogFile(const std::filesystem::path& file_path) {
    const std::string filename = toLower(file_path.filename().string());
    return filename == "log" || filename.find(".log") != std::string::npos || filename.find("log.") != std::string::npos;
}

int64_t LogParser::parseTimestampMillis(const std::string& line) {
    static const std::regex full_datetime(R"((\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:[.,](\d{1,3}))?)");
    std::smatch match;
    if (std::regex_search(line, match, full_datetime)) {
        std::tm tm{};
        tm.tm_year = std::stoi(match[1].str()) - 1900;
        tm.tm_mon = std::stoi(match[2].str()) - 1;
        tm.tm_mday = std::stoi(match[3].str());
        tm.tm_hour = std::stoi(match[4].str());
        tm.tm_min = std::stoi(match[5].str());
        tm.tm_sec = std::stoi(match[6].str());

        int millis = 0;
        if (match[7].matched) {
            std::string fraction = match[7].str();
            while (fraction.size() < 3) {
                fraction.push_back('0');
            }
            millis = std::stoi(fraction.substr(0, 3));
        }

        const std::time_t seconds = toLocalTimeT(&tm);
        if (seconds > 0) {
            return static_cast<int64_t>(seconds) * 1000 + millis;
        }
    }

    return currentUnixMillis();
}

std::string LogParser::parseLevel(const std::string& line) {
    static const std::regex level_regex(R"((TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|WRN|ERR|INF|DBG))", std::regex::icase);
    std::smatch match;
    if (std::regex_search(line, match, level_regex)) {
        std::string level = toLower(match[1].str());
        if (level == "wrn") {
            return "warn";
        }
        if (level == "err") {
            return "error";
        }
        if (level == "inf") {
            return "info";
        }
        if (level == "dbg") {
            return "debug";
        }
        if (level == "warning") {
            return "warn";
        }
        return level;
    }
    return "info";
}

std::string LogParser::parseMessage(const std::string& line) {
    const auto bracket = line.find("] ");
    if (bracket != std::string::npos && bracket + 2 < line.size()) {
        return line.substr(bracket + 2);
    }

    static const std::regex level_prefix(R"(^.*?(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|WRN|ERR|INF|DBG)\s*[:\]]?\s*)", std::regex::icase);
    return std::regex_replace(line, level_prefix, "");
}

std::string LogParser::makeLogId(const std::string& package_id, const std::string& module_name, int line_no) {
    std::ostringstream oss;
    oss << (package_id.empty() ? "pkg" : package_id) << "-" << module_name << "-" << line_no;
    return oss.str();
}

} // namespace robotops::log_service
