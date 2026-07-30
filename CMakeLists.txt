cmake_minimum_required(VERSION 3.16)

project(RobotOpsAI VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Protobuf REQUIRED)

get_filename_component(CPP_MICROSERVICE_KIT_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../cpp-microservice-kit"
    ABSOLUTE)

add_subdirectory(
    "${CPP_MICROSERVICE_KIT_DIR}"
    "${CMAKE_BINARY_DIR}/third_party/cpp-microservice-kit")

set(ROBOTOPS_PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/proto")
set(ROBOTOPS_PROTO_GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated/proto")

set(ROBOTOPS_PROTO_FILES
    "${ROBOTOPS_PROTO_DIR}/common.proto"
    "${ROBOTOPS_PROTO_DIR}/log.proto")

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

