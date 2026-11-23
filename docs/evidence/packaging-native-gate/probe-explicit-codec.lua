-- Disposable test client only. No SavedVariables, network or dynamic Lua loader.
local expected = string.rep("market partition compression interoperability ", 100)
local method = Enum and Enum.CompressionMethod and Enum.CompressionMethod.Deflate
print("PACKAGING_EXPLICIT_METHOD", tostring(method))
for name, vector in pairs({
    raw="7cqxDYBACEDRVVgNDQVRDsLRuL1xDJPfveKF9mUjpT0+nkvOjGrb+7Ovsc6y1sNvn0eCzWaz2Ww2m81ms9lsNpv9k/0C",
    zlib="eJztyrENgEAIQNFVWA0NBVEOwtG4vXEMk9+94oX2ZSOlPT6eS86Matv7s6+xzrLWw2+fR4LNZrPZbDabzWaz2Ww2m/2T/QJ+8yoC"
}) do
    local ok, value = pcall(function()
        return C_EncodingUtil.DecompressString(C_EncodingUtil.DecodeBase64(vector), method)
    end)
    print("PACKAGING_EXPLICIT_VECTOR", name, ok, value == expected, value and #value)
end
local ok, packed = pcall(function() return C_EncodingUtil.CompressString(expected, method) end)
print("PACKAGING_EXPLICIT_COMPRESSED", ok, packed and #packed, packed == expected)
