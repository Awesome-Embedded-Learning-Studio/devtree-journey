cmake_minimum_required(VERSION 3.28)

project(edtc
    VERSION 0.1.0
    DESCRIPTION "C++26 DTB/FDT device-tree toolkit"
    LANGUAGES CXX)

# --- 全局设定 ---------------------------------------------------------------
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# clangd 靠这个拿编译参数(build/compile_commands.json,根目录有软链)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 不用 C++ modules,关掉 GCC 模块依赖扫描
# (否则命令里混入 -fmodules-ts 等 GCC 私有参数,clangd 报 unknown argument)
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)

add_compile_options(-Wall -Wextra -Wpedantic)

add_library(edtc STATIC src/base/file_reader.cpp)
add_library(edtc::edtc ALIAS edtc)

target_compile_features(edtc PUBLIC cxx_std_26)
target_include_directories(edtc PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)

# --- 示例层 -----------------------------------------------------------------
add_executable(bootstrap example/00_bootstrap/main.cpp)
target_link_libraries(bootstrap PRIVATE edtc::edtc)
