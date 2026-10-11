/**
 * @file    include/edtc/base/endian.hpp
 * @brief   Compile-time host-to-big/little endian conversion helpers.
 *
 * Wraps std::byteswap behind order-specific conversions that resolve to the
 * identity function whenever the host already matches the target layout.
 *
 * @author  charliechen
 * @date    2026-09-27
 * @version 0.1.0
 * @since   0.1.0
 * @ingroup edtc_base
 */

#pragma once
#include <bit>
#include <cstdint>

namespace edtc::base {

/**
 * @brief  Converts a 32-bit value to big-endian byte order.
 *
 * @param[in]  bytes  The value in host byte order.
 * @return          The value in big-endian byte order.
 * @throws          None
 * @note            Usable in constant expressions; resolves to the identity
 *                  conversion on a big-endian host.
 * @warning         None
 * @since           0.1.0
 * @ingroup         edtc_base
 */
constexpr std::uint32_t ToBigEndian(std::uint32_t bytes) {
    if constexpr (std::endian::native == std::endian::little) {
        bytes = std::byteswap(bytes);
    }
    return bytes;
}

/**
 * @brief  Converts a 32-bit value to little-endian byte order.
 *
 * @param[in]  bytes  The value in host byte order.
 * @return          The value in little-endian byte order.
 * @throws          None
 * @note            Usable in constant expressions; resolves to the identity
 *                  conversion on a little-endian host.
 * @warning         None
 * @since           0.1.0
 * @ingroup         edtc_base
 */
constexpr std::uint32_t ToLittleEndian(std::uint32_t bytes) {
    if constexpr (std::endian::native == std::endian::big) {
        bytes = std::byteswap(bytes);
    }
    return bytes;
}

}  // namespace edtc::base
