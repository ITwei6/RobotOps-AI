cmake_minimum_required(VERSION 3.16)

project(RobotOpsAI VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Protobuf REQUIRED)
find_package(Threads REQUIRED)

set(CPP_MICROSERVICE_KIT_DIR "" CACHE PATH "Path to cpp-microservice-kit")

if(NOT CPP_MICROSERVICE_KIT_DIR)
    set(CPP_MICROSERVICE_KIT_CANDIDATES
        "${CMAKE_CURRENT_SOURCE_DIR}/../cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/third_party/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../DeviceOps/third_party/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../projects/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../cpp-microservice-kit")

    foreach(CANDIDATE ${CPP_MICROSERVICE_KIT_CANDIDATES})
        if(EXISTS "${CANDIDATE}/CMakeLists.txt")
            set(CPP_MICROSERVICE_KIT_DIR "${CANDIDATE}")
            break()
        endif()
    endforeach()
endif()

if(NOT CPP_MICROSERVICE_KIT_DIR OR NOT EXISTS "${CPP_MICROSERVICE_KIT_DIR}/CMakeLists.txt")
    message(FATAL_ERROR
        "cpp-microservice-kit not found. "
        "Configure with -DCPP_MICROSERVICE_KIT_DIR=/path/to/cpp-microservice-kit")
endif()

get_filename_component(CPP_MICROSERVICE_KIT_DIR
    "${CPP_MICROSERVICE_KIT_DIR}"
    ABSOLUTE)

message(STATUS "Using cpp-microservice-kit: ${CPP_MICROSERVICE_KIT_DIR}")

option(ROBOTOPS_USE_FULL_CPP_MICROSERVICE_KIT
    "Build cpp-microservice-kit with its full dependency set"
    OFF)

if(ROBOTOPS_USE_FULL_CPP_MICROSERVICE_KIT)
    add_subdirectory(
        "${CPP_MICROSERVICE_KIT_DIR}"
        "${CMAKE_BINARY_DIR}/third_party/cpp-microservice-kit")
    set(ROBOTOPS_SCAFFOLD_TARGET tew_scaffold)
else()
    set(ROBOTOPS_MINIMAL_SCAFFOLD_LIBS
        brpc
        leveldb
        protobuf
        ssl
        crypto
        gflags
        spdlog
        fmt)

    set(ROBOTOPS_MINIMAL_SCAFFOLD_LINK_LIBS)
    foreach(LIB_NAME ${ROBOTOPS_MINIMAL_SCAFFOLD_LIBS})
        find_library(ROBOTOPS_${LIB_NAME}_LIBRARY
            NAMES ${LIB_NAME} ${LIB_NAME}_nothreads
            PATHS /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib)
        if(NOT ROBOTOPS_${LIB_NAME}_LIBRARY)
            message(FATAL_ERROR "Required library for log-service scaffold not found: ${LIB_NAME}")
        endif()
        list(APPEND ROBOTOPS_MINIMAL_SCAFFOLD_LINK_LIBS "${ROBOTOPS_${LIB_NAME}_LIBRARY}")
    endforeach()

    add_library(robotops_tew_scaffold_minimal STATIC
        "${CPP_MICROSERVICE_KIT_DIR}/source/log.cc"
        "${CPP_MICROSERVICE_KIT_DIR}/source/rpc.cc")

    target_include_directories(robotops_tew_scaffold_minimal
        PUBLIC
            "${CPP_MICROSERVICE_KIT_DIR}/source")

    target_link_libraries(robotops_tew_scaffold_minimal
        PUBLIC
            ${ROBOTOPS_MINIMAL_SCAFFOLD_LINK_LIBS}
            Threads::Threads
            dl)

    set(ROBOTOPS_SCAFFOLD_TARGET robotops_tew_scaffold_minimal)
endif()

set(ROBOTOPS_PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/proto")
set(ROBOTOPS_PROTO_GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated/proto")

set(ROBOTOPS_PROTO_FILES
    "${ROBOTOPS_PROTO_DIR}/common.proto"
    "${ROBOTOPS_PROTO_DIR}/log.proto"
    "${ROBOTOPS_PROTO_DIR}/ticket_diagnosis.proto")

set(ROBOTOPS_PROTO_SRCS)
set(ROBOTOPS_PROTO_HDRS)

foreach(PROTO_FILE ${ROBOTOPS_PROTO_FILES})
    get_filename_component(PROTO_NAME "${PROTO_FILE}" NAME_WE)
    set(GENERATED_SRC "${ROBOTOPS_PROTO_GENERATED_DIR}/${PROTO_NAME}.pb.cc")
    set(GENERATED_HDR "${ROBOTOPS_PROTO_GENERATED_DIR}/${PROTO_NAME}.pb.h")

    add_custom_command(
        OUTPUT "${GENERATED_SRC}" "${GENERATED_HDR}"
        COMMAND ${CMAKE_COMMAND} -E make_directory "${ROBOTOPS_PROTO_GENERATED_DIR}"
        COMMAND ${Protobuf_PROTOC_EXECUTABLE}
            --proto_path=${ROBOTOPS_PROTO_DIR}
            --cpp_out=${ROBOTOPS_PROTO_GENERATED_DIR}
            "${PROTO_FILE}"
        DEPENDS ${ROBOTOPS_PROTO_FILES}
        COMMENT "Generating C++ protobuf source for ${PROTO_NAME}.proto"
        VERBATIM)

    list(APPEND ROBOTOPS_PROTO_SRCS "${GENERATED_SRC}")
    list(APPEND ROBOTOPS_PROTO_HDRS "${GENERATED_HDR}")
endforeach()

add_library(robotops_proto STATIC
    ${ROBOTOPS_PROTO_SRCS}
    ${ROBOTOPS_PROTO_HDRS})

target_include_directories(robotops_proto
    PUBLIC
        "${ROBOTOPS_PROTO_GENERATED_DIR}"
        ${Protobuf_INCLUDE_DIRS})

target_link_libraries(robotops_proto
    PUBLIC
        ${Protobuf_LIBRARIES})

add_subdirectory(backend/services/log_service)
add_subdirectory(backend/services/ticket_diagnosis_service)
