/**
 * @file    include/edtc/base/file_reader.hpp
 * @brief   RAII reader that owns a read-only std::FILE handle.
 *
 * Declares a move-only reader enforcing a strong invariant: a constructed
 * object always refers to an open file, and the handle is closed exactly
 * once on destruction or ownership transfer.
 *
 * @author  charliechen
 * @date    2026-09-27
 * @version 0.1.0
 * @since   0.1.0
 * @ingroup edtc_base
 */

#pragma once

#include <cstddef>
#include <cstdio>
#include <filesystem>
#include <span>
#include <system_error>
#include <vector>

namespace edtc::base {

/**
 * @brief  Reports a failure to open a file for reading.
 *
 * @ingroup edtc_base
 */
class FileOpenError : public std::system_error {
public:
    /**
     * @brief  Constructs the error for a path and errno value.
     *
     * @param[in]  path  The path that failed to open.
     * @param[in]  err   The errno value captured at the open call.
     * @throws          None
     * @note            The errno value stays accessible through code().
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    FileOpenError(const std::filesystem::path& path, int err);
};

/**
 * @brief  Move-only owner of a read-only std::FILE handle.
 *
 * @ingroup edtc_base
 */
class FileReader {
public:
    /**
     * @brief  Opens a file for binary reading.
     *
     * @param[in]  path  Path of the file to open.
     * @throws          FileOpenError when the file cannot be opened.
     * @note            The object holds no half-open state: construction
     *                  either yields a valid reader or throws.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    explicit FileReader(const std::filesystem::path& path);

    FileReader(const FileReader&) = delete ("Don't Copy FILE*, Double Close is not permitted");
    FileReader& operator=(const FileReader&) =
        delete ("Don't Copy FILE*, Double Close is not permitted");

    /**
     * @brief  Takes ownership of the handle held by another reader.
     *
     * @param[in, out]  other  The reader to transfer from; holds no file
     *                         afterwards.
     * @throws          None
     * @note            Marked noexcept; a moved-from reader is inert.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    FileReader(FileReader&& other) noexcept;

    /**
     * @brief  Releases the current handle and adopts the one held by other.
     *
     * @param[in, out]  other  The reader to transfer from; holds no file
     *                         afterwards.
     * @throws          None
     * @note            Self-assignment is a no-op.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    FileReader& operator=(FileReader&& other) noexcept;

    /**
     * @brief  Closes the owned handle, if any.
     *
     * @throws          None
     * @note            Closing a read-only handle does not fail; this
     *                  destructor never throws.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    ~FileReader();

    /**
     * @brief  Reads up to dst.size() bytes into the destination buffer.
     *
     * @param[out]  dst  Buffer receiving the bytes read.
     * @return          The number of bytes actually read; zero at end of
     *                  file.
     * @throws          None
     * @note            A short read does not indicate an error; query the
     *                  stream state when a full read is required.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    [[nodiscard]] std::size_t read(std::span<std::byte> dst) noexcept;

    /**
     * @brief  Reads exactly dst.size() bytes into the destination buffer.
     *
     * @param[out]  dst  Buffer receiving the bytes read.
     * @throws          std::runtime_error when the file ends before the
     *                  buffer is full.
     * @note            Intended for fixed-size structures such as an FDT
     *                  header block.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    void read_exact(std::span<std::byte> dst);

    /**
     * @brief  Returns the size of the file in bytes.
     *
     * @return          The total number of bytes in the file.
     * @throws          None
     * @note            Restores the original read position on return.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    [[nodiscard]] std::size_t size() const;

    /**
     * @brief  Reads the remaining file content into a byte vector.
     *
     * @return          The complete file contents, starting at the current
     *                  read position.
     * @throws          std::bad_alloc when the buffer allocation fails.
     * @note            The buffer is zero-initialized before the read fills
     *                  it.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    [[nodiscard]] std::vector<std::byte> read_all();

private:
    /**
     * @brief  Closes the owned handle and clears the pointer.
     *
     * @throws          None
     * @note            Safe to call when no handle is held.
     * @warning         None
     * @since           0.1.0
     * @ingroup         edtc_base
     */
    void reset() noexcept;

    std::FILE* file_{nullptr};
};

}  // namespace edtc::base
