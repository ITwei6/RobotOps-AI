#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include "log.pb.h"

namespace robotops::log_service {

struct ParsedLogFile {
    robotops::log::LogFileInfo file;
    std::vector<robotops::log::ModuleLogEntry> logs;
};

class LogParser {
public:
    std::vector<ParsedLogFile> parsePackage(
        const std::string& bug_id,
        const std::string& package_id,
        const std::string& package_path,
        robotops::common::RobotType robot_type,
        const std::string& robot_sn) const;

private:
    ParsedLogFile parseFile(
        const std::filesystem::path& root,
        const std::filesystem::path& file_path,
        const std::string& bug_id,
        const std::string& package_id,
        robotops::common::RobotType robot_type,
        const std::string& robot_sn) const;

    static std::string moduleNameFromPath(const std::filesystem::path& root, const std::filesystem::path& file_path);
    static bool isLogFile(const std::filesystem::path& file_path);
    static int64_t parseTimestampMillis(const std::string& line);
    static std::string parseLevel(const std::string& line);
    static std::string parseMessage(const std::string& line);
    static std::string makeLogId(const std::string& package_id, const std::string& module_name, int line_no);
    static std::filesystem::path preparePackageRoot(
        const std::string& package_id,
        const std::filesystem::path& package_path,
        std::filesystem::path* temporary_root);
    static std::filesystem::path selectContentRoot(const std::filesystem::path& extraction_root);
    static void validateArchiveEntries(const std::filesystem::path& archive_path);
    static void validateExtractedTree(const std::filesystem::path& extraction_root);
};

} // namespace robotops::log_service
