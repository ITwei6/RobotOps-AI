#include "log_service/log_parser.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <system_error>
#include <unistd.h>

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

constexpr uintmax_t kMaxArchiveEntries = 20000;
constexpr uintmax_t kMaxExtractedBytes = 1024ULL * 1024ULL * 1024ULL;

std::string shellQuote(const std::string& value) {
    std::string quoted("'");
    for (const char ch : value) {
        if (ch == '\'') {
            quoted += "'\\''";
        } else {
            quoted += ch;
        }
    }
    quoted += '\'';
    return quoted;
}

std::string runCommand(const std::string& command) {
    FILE* pipe = ::popen(command.c_str(), "r");
    if (pipe == nullptr) {
        throw std::runtime_error("failed to start archive command");
    }

    std::string output;
    char buffer[4096];
    while (std::fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output.append(buffer);
        if (output.size() > 4 * 1024 * 1024) {
            ::pclose(pipe);
            throw std::runtime_error("archive listing is too large");
        }
    }

    const int status = ::pclose(pipe);
    if (status != 0) {
        throw std::runtime_error("archive command failed");
    }
    return output;
}

bool isArchive(const std::filesystem::path& path) {
    const std::string name = toLower(path.filename().string());
    const auto endsWith = [&name](const std::string& suffix) {
        return name.size() >= suffix.size() && name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0;
    };
    return path.has_extension() && (endsWith(".zip") || endsWith(".tar")
        || endsWith(".tar.gz") || endsWith(".tgz"));
}

bool isTarGz(const std::filesystem::path& path) {
    const std::string name = toLower(path.filename().string());
    return (name.size() >= 7 && name.compare(name.size() - 7, 7, ".tar.gz") == 0)
        || (name.size() >= 4 && name.compare(name.size() - 4, 4, ".tgz") == 0);
}

std::string zipListCommand(const std::string& archive) {
    return "if command -v unzip >/dev/null 2>&1; then unzip -Z1 " + archive
        + "; else python3 -c "
        + shellQuote("import sys, zipfile; print('\\n'.join(item.filename for item in zipfile.ZipFile(sys.argv[1]).infolist()))")
        + " " + archive + "; fi";
}

std::string zipExtractCommand(const std::string& archive, const std::string& destination) {
    return "if command -v unzip >/dev/null 2>&1; then unzip -qq -o " + archive + " -d " + destination
        + "; else python3 -c "
        + shellQuote("import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])")
        + " " + archive + " " + destination + "; fi";
}

bool unsafeArchiveEntry(const std::string& raw_entry) {
    if (raw_entry.empty() || raw_entry.front() == '/' || raw_entry.front() == '\\'
        || (raw_entry.size() > 1 && raw_entry[1] == ':')) {
        return true;
    }
    const std::filesystem::path entry(raw_entry);
    for (const auto& component : entry) {
        if (component == "..") {
            return true;
        }
    }
    return false;
}

std::string sanitizedPackageId(const std::string& package_id) {
    std::string value;
    for (const char ch : package_id) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '-' || ch == '_') {
            value += ch;
        }
    }
    if (value.empty()) {
        value = "package";
    }
    return value.substr(0, 48);
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

    const std::filesystem::path input_path(package_path);
    if (!std::filesystem::exists(input_path)) {
        throw std::invalid_argument("package_path does not exist: " + package_path);
    }

    std::filesystem::path temporary_root;
    const std::filesystem::path root = preparePackageRoot(package_id, input_path, &temporary_root);
    struct TemporaryRootGuard {
        std::filesystem::path path;
        ~TemporaryRootGuard() {
            if (!path.empty()) {
                std::error_code error;
                std::filesystem::remove_all(path, error);
            }
        }
    } temporary_guard{temporary_root};

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

std::filesystem::path LogParser::preparePackageRoot(
    const std::string& package_id,
    const std::filesystem::path& package_path,
    std::filesystem::path* temporary_root) {
    if (std::filesystem::is_directory(package_path)) {
        return package_path;
    }
    if (!std::filesystem::is_regular_file(package_path) || !isArchive(package_path)) {
        throw std::invalid_argument("package_path must be a directory or .zip/.tar/.tar.gz/.tgz archive");
    }

    const auto extraction_root = std::filesystem::temp_directory_path()
        / ("robotops-log-" + sanitizedPackageId(package_id) + "-" + std::to_string(::getpid()));
    std::error_code error;
    std::filesystem::remove_all(extraction_root, error);
    std::filesystem::create_directories(extraction_root);
    if (!std::filesystem::exists(extraction_root)) {
        throw std::runtime_error("failed to create archive extraction directory");
    }

    struct ExtractionGuard {
        std::filesystem::path path;
        bool keep = false;
        ~ExtractionGuard() {
            if (!keep) {
                std::error_code cleanup_error;
                std::filesystem::remove_all(path, cleanup_error);
            }
        }
    } extraction_guard{extraction_root};
    *temporary_root = extraction_root;
    validateArchiveEntries(package_path);
    const std::string archive = shellQuote(package_path.string());
    const std::string destination = shellQuote(extraction_root.string());
    const std::string name = toLower(package_path.filename().string());
    if (name.size() >= 4 && name.compare(name.size() - 4, 4, ".zip") == 0) {
        runCommand(zipExtractCommand(archive, destination));
    } else if (isTarGz(package_path)) {
        runCommand("tar -xzf " + archive + " -C " + destination + " --no-same-owner --no-same-permissions");
    } else {
        runCommand("tar -xf " + archive + " -C " + destination + " --no-same-owner --no-same-permissions");
    }
    validateExtractedTree(extraction_root);
    extraction_guard.keep = true;
    return selectContentRoot(extraction_root);
}

std::filesystem::path LogParser::selectContentRoot(const std::filesystem::path& extraction_root) {
    std::vector<std::filesystem::directory_entry> entries;
    for (const auto& entry : std::filesystem::directory_iterator(extraction_root)) {
        entries.push_back(entry);
    }
    if (entries.size() == 1 && entries.front().is_directory()) {
        return entries.front().path();
    }
    return extraction_root;
}

void LogParser::validateArchiveEntries(const std::filesystem::path& archive_path) {
    const std::string name = toLower(archive_path.filename().string());
    const std::string archive = shellQuote(archive_path.string());
    const bool isZip = name.size() >= 4 && name.compare(name.size() - 4, 4, ".zip") == 0;
    const std::string command = isZip
        ? zipListCommand(archive)
        : (isTarGz(archive_path) ? "tar -tzf " + archive : "tar -tf " + archive);
    const std::string listing = runCommand(command);
    size_t entries = 0;
    size_t start = 0;
    while (start < listing.size()) {
        const size_t end = listing.find('\n', start);
        const std::string entry = listing.substr(start, end == std::string::npos ? std::string::npos : end - start);
        if (!entry.empty()) {
            if (++entries > kMaxArchiveEntries || unsafeArchiveEntry(entry)) {
                throw std::invalid_argument("archive contains unsafe or too many entries");
            }
        }
        if (end == std::string::npos) {
            break;
        }
        start = end + 1;
    }
}

void LogParser::validateExtractedTree(const std::filesystem::path& extraction_root) {
    uintmax_t total_bytes = 0;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(
             extraction_root, std::filesystem::directory_options::skip_permission_denied)) {
        if (entry.is_symlink()) {
            throw std::invalid_argument("archive symlinks are not allowed");
        }
        if (!entry.is_regular_file()) {
            continue;
        }
        std::error_code error;
        const auto size = entry.file_size(error);
        if (error || size > kMaxExtractedBytes || total_bytes > kMaxExtractedBytes - size) {
            throw std::invalid_argument("extracted archive exceeds size limit");
        }
        total_bytes += size;
    }
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
