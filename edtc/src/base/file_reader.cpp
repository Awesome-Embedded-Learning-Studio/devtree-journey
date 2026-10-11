#include "edtc/base/file_reader.hpp"

#include <cerrno>
#include <stdexcept>
#include <string>
#include <utility>

namespace edtc::base {

FileOpenError::FileOpenError(const std::filesystem::path& path, int err)
    : std::system_error{err, std::generic_category(), "cannot open '" + path.string() + "'"} {}

FileReader::FileReader(const std::filesystem::path& path) : file_{std::fopen(path.c_str(), "rb")} {
    if (!file_) {
        throw FileOpenError{path, errno};
    }
}

FileReader::FileReader(FileReader&& other) noexcept : file_{std::exchange(other.file_, nullptr)} {}

FileReader& FileReader::operator=(FileReader&& other) noexcept {
    if (this != &other) {
        reset();
        file_ = std::exchange(other.file_, nullptr);
    }
    return *this;
}

FileReader::~FileReader() {
    reset();
}

std::size_t FileReader::read(std::span<std::byte> dst) noexcept {
    return std::fread(dst.data(), 1, dst.size(), file_);
}

void FileReader::read_exact(std::span<std::byte> dst) {
    if (read(dst) != dst.size()) {
        throw std::runtime_error{"edtc: unexpected end of file"};
    }
}

std::size_t FileReader::size() const {
    const long kCurrent = std::ftell(file_);
    std::fseek(file_, 0, SEEK_END);
    const long kEnd = std::ftell(file_);
    std::fseek(file_, kCurrent, SEEK_SET);
    return static_cast<std::size_t>(kEnd);
}

std::vector<std::byte> FileReader::read_all() {
    std::vector<std::byte> buf(size());
    buf.resize(read(buf));
    return buf;
}

void FileReader::reset() noexcept {
    if (file_) {
        // noexcept 路径上绝不抛;只读句柄的 fclose 不会失败
        // (如果是写句柄,fclose 刷缓冲可能失败,这里就得另作安排)
        std::fclose(file_);
        file_ = nullptr;
    }
}

}  // namespace edtc::base
