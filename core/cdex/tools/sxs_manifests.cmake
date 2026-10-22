# Add the shared ReactOS SxS dependency before linking packaged modules.
# This extension is loaded only when CDEX_SXS_CMAKE is supplied.
if(CMAKE_VERSION VERSION_LESS 3.19 OR MSVC)
    message(FATAL_ERROR "CDEX SxS manifests require CMake 3.19+ and windres")
endif()

find_program(CDEX_SXS_PYTHON python3 REQUIRED)

# Packaging-owned helper and build-only resource catalog; neither is a DLL path.
set(CDEX_SXS_GENERATOR "${CMAKE_CURRENT_LIST_DIR}/prepare_sxs_manifests.py")
set(CDEX_SXS_RESOURCE_DIR "${CMAKE_BINARY_DIR}/cdex-sxs-resources")

# Reuse the Makefile's target list instead of maintaining a second module list.
separate_arguments(CDEX_SXS_TARGETS UNIX_COMMAND "${CDEX_SXS_TARGETS}")


#[[
Schedule manifest preparation for a packaged Win32 target.
Run at the end of its directory so all sources, flags and dependencies are set.
]]
function(cdex_schedule_sxs_resources target module_type)
    if(NOT target IN_LIST CDEX_SXS_TARGETS)
        return()
    endif()

    if(NOT module_type MATCHES "^(win32gui|win32cui|win32dll|win32ocx|cpl)$")
        return()
    endif()

    # DEFER evaluates arguments later; capture the current target name now.
    cmake_language(EVAL CODE
        "cmake_language(DEFER CALL cdex_prepare_sxs_resources [[${target}]])")
endfunction()


#[[
Create res_target from the RC sources in ARGN, inheriting source_target's setup.
The object library produces RES data for manifest merging, not linker objects.
]]
function(cdex_add_res_library source_target res_target)
    add_library(${res_target} OBJECT EXCLUDE_FROM_ALL ${ARGN})

    # Keep the module's definitions and transitive library usage requirements.
    target_include_directories(${res_target} PRIVATE
        "$<TARGET_PROPERTY:${source_target},INCLUDE_DIRECTORIES>")
    target_compile_definitions(${res_target} PRIVATE
        "$<TARGET_PROPERTY:${source_target},COMPILE_DEFINITIONS>")
    target_compile_options(${res_target} PRIVATE
        "$<TARGET_PROPERTY:${source_target},COMPILE_OPTIONS>")
    target_link_libraries(${res_target} PRIVATE
        "$<TARGET_PROPERTY:${source_target},LINK_LIBRARIES>")

    get_target_property(compile_flags ${source_target} COMPILE_FLAGS)
    if(compile_flags)
        set_property(TARGET ${res_target} PROPERTY COMPILE_FLAGS "${compile_flags}")
    endif()

    # Compile directly to RES: windres loses language IDs in COFF -> RES.
    # CMake filters target RC flags; this source option applies only to res_target.
    set_property(SOURCE ${ARGN} APPEND PROPERTY COMPILE_OPTIONS
        "$<$<STREQUAL:$<TARGET_PROPERTY:NAME>,${res_target}>:--output-format=res>")

    # Generated headers must exist before this separate RC target can compile.
    get_target_property(build_dependencies ${source_target} MANUALLY_ADDED_DEPENDENCIES)
    if(build_dependencies)
        add_dependencies(${res_target} ${build_dependencies})
    endif()
endfunction()


#[[
Replace a module's RC sources with one resource object containing SxS manifests.
Keep other sources on the original target and index its RES file for packaging.
]]
function(cdex_prepare_sxs_resources target)
    get_target_property(sources ${target} SOURCES)
    set(rc_sources)
    set(program_sources)
    set(has_program_language FALSE)

    foreach(source IN LISTS sources)
        if(source MATCHES "\\.[rR][cC]$")
            list(APPEND rc_sources "${source}")
        else()
            list(APPEND program_sources "${source}")
            get_source_file_property(language "${source}" LANGUAGE)
            if(language AND NOT language STREQUAL "RC")
                set(has_program_language TRUE)
            endif()
        endif()
    endforeach()

    set(resource_inputs)
    set(resource_dependencies)

    if(rc_sources)
        set(res_target "${target}_sxs_resources")
        cdex_add_res_library(${target} ${res_target} ${rc_sources})

        set(resource_inputs "$<TARGET_OBJECTS:${res_target}>")
        set(resource_dependencies ${res_target} ${resource_inputs})
    endif()

    get_target_property(target_type ${target} TYPE)
    if(target_type STREQUAL "EXECUTABLE")
        set(module_kind exe)
    else()
        set(module_kind dll)
    endif()

    set(resource_file "${CMAKE_CURRENT_BINARY_DIR}/${target}.sxs.res")
    set(resource_object "${CMAKE_CURRENT_BINARY_DIR}/${target}.sxs.res.obj")

    add_custom_command(
        OUTPUT "${resource_object}" "${resource_file}"
        COMMAND "${CDEX_SXS_PYTHON}" "${CDEX_SXS_GENERATOR}" resources
            --compiler "${CMAKE_RC_COMPILER}"
            --kind "${module_kind}"
            --module "$<TARGET_FILE_NAME:${target}>"
            --output "${resource_file}"
            --object "${resource_object}"
            --inputs ${resource_inputs}
        DEPENDS ${resource_dependencies} "${CDEX_SXS_GENERATOR}"
        COMMAND_EXPAND_LISTS
        VERBATIM)

    set_source_files_properties("${resource_object}" PROPERTIES
        EXTERNAL_OBJECT TRUE
        GENERATED TRUE)
    set_property(TARGET ${target} PROPERTY SOURCES
        ${program_sources} "${resource_object}")

    if(NOT has_program_language)
        # Pure-resource modules previously linked through the RC rule's C compiler.
        set_property(TARGET ${target} PROPERTY LINKER_LANGUAGE C)
    endif()

    # Use the actual output name, including aliases such as odbccp32i.cpl.
    file(GENERATE
        OUTPUT "${CDEX_SXS_RESOURCE_DIR}/$<TARGET_FILE_NAME:${target}>.res-path"
        CONTENT "${resource_file}")
endfunction()
