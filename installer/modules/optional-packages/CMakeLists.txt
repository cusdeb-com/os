cmake_minimum_required( VERSION 3.16 )
project( optional-packages LANGUAGES CXX )

set( CMAKE_CXX_STANDARD 17 )
set( CMAKE_CXX_STANDARD_REQUIRED ON )
set( CMAKE_AUTOMOC ON )

find_package( Qt6 REQUIRED COMPONENTS Core Widgets Gui )

# Calamares runtime paths on Debian trixie.
# NOTE: development package calamares-dev is not available, so include and
# library directories are set manually below.
set( CALAMARES_INCLUDE_DIR "/usr/include/libcalamares" )
set( CALAMARES_LIB_DIR "/usr/lib/x86_64-linux-gnu" )

add_library( calamares_viewmodule_optional-packages MODULE
    OptionalPackagesPage.cpp
    OptionalPackagesPage.h
    ViewStep.cpp
    ViewStep.h
)

set_target_properties( calamares_viewmodule_optional-packages PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
)

# Export macros required by Calamares headers to mark plugin entry points.
target_compile_definitions( calamares_viewmodule_optional-packages PRIVATE
    PLUGINDLLEXPORT_PRO
    DLLEXPORT_PRO
    UIDLLEXPORT_PRO
)

target_include_directories( calamares_viewmodule_optional-packages PRIVATE
    ${CALAMARES_INCLUDE_DIR}
)

target_link_libraries( calamares_viewmodule_optional-packages PRIVATE
    Qt6::Core
    Qt6::Widgets
    Qt6::Gui
    ${CALAMARES_LIB_DIR}/libcalamares.so
    ${CALAMARES_LIB_DIR}/libcalamaresui.so
)

# Keep module.desc next to the built shared object for local testing.
configure_file( module.desc ${CMAKE_CURRENT_BINARY_DIR}/module.desc COPYONLY )

install( TARGETS calamares_viewmodule_optional-packages
    LIBRARY DESTINATION ${CALAMARES_LIB_DIR}/calamares/modules/optional-packages
)
install( FILES module.desc
    DESTINATION ${CALAMARES_LIB_DIR}/calamares/modules/optional-packages
)
