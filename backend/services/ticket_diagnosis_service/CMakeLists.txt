add_executable(ticket_diagnosis_service
    src/agent_client.cc
    src/ticket_diagnosis_store.cc
    src/ticket_diagnosis_service_impl.cc
    src/main.cc)

find_library(ROBOTOPS_CPR_LIBRARY cpr REQUIRED)
find_library(ROBOTOPS_JSONCPP_LIBRARY jsoncpp REQUIRED)

target_include_directories(ticket_diagnosis_service
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        /usr/include/jsoncpp)

target_link_libraries(ticket_diagnosis_service
    PRIVATE
        ${ROBOTOPS_SCAFFOLD_TARGET}
        robotops_proto
        ${ROBOTOPS_CPR_LIBRARY}
        ${ROBOTOPS_JSONCPP_LIBRARY})
