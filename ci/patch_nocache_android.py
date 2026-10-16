#!/usr/bin/env python3
"""
MiniCPM-V-Apps Android 构建兼容性补丁
======================================
上游 llama.cpp-omni 的 src/llama-moe-slot.cpp 中，MoE experts 页缓存旁路使用了
fcntl(fd, F_NOCACHE, ...)。该 fcntl 命令只存在于 Darwin (macOS/iOS) 与 FreeBSD，
Android bionic / Linux glibc 均无定义 → 上游当前版本 Android 端编译失败（iOS 端正常）。

本脚本给两处调用加 #if defined(__APPLE__) || defined(__FreeBSD__) 保护；
Android 退回经 page cache 的正常读取（功能不受影响，仅 SSD 流式加载的缓存策略退化）。

用法（在仓库根目录，即 llama.cpp-omni/ 所在目录）：
    python3 ci/patch_nocache_android.py

幂等：重复运行不会二次包裹。保留原文件行尾（CRLF/LF）。
"""
import sys

P = "llama.cpp-omni/src/llama-moe-slot.cpp"

OLD1 = (
    "        for (const auto & kv : fds) {\n"
    "            if (fcntl(kv.second, F_NOCACHE, on ? 1 : 0) != 0) {\n"
    '                moe_log("F_NOCACHE 切换失败: %s", std::strerror(errno));\n'
    "            }\n"
    "        }"
)
NEW1 = (
    "#if defined(__APPLE__) || defined(__FreeBSD__)\n"
    + OLD1
    + "\n#else\n"
    "        (void)on;  // Android/Linux: no F_NOCACHE, read via page cache\n"
    "#endif"
)

OLD2 = (
    "        const int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);\n"
    "        if (experts_nocache_desired() && fcntl(fd, F_NOCACHE, 1) != 0) {\n"
    '            moe_log("F_NOCACHE 设置失败: %s", std::strerror(errno));\n'
    "        }"
)
NEW2 = (
    "        const int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);\n"
    "#if defined(__APPLE__) || defined(__FreeBSD__)\n"
    "        if (experts_nocache_desired() && fcntl(fd, F_NOCACHE, 1) != 0) {\n"
    '            moe_log("F_NOCACHE 设置失败: %s", std::strerror(errno));\n'
    "        }\n"
    "#endif"
)


def patch_once(s, old, new, tag):
    if new in s:
        print(f"[skip] {tag}: already patched")
        return s
    if old not in s:
        print(f"[fail] {tag}: target not found")
        sys.exit(1)
    print(f"[ok] {tag}: patched")
    return s.replace(old, new, 1)


def main():
    try:
        raw = open(P, "rb").read()
    except FileNotFoundError:
        print(f"[fail] {P} not found — run from the repository root")
        sys.exit(1)

    eol = "\r\n" if b"\r\n" in raw else "\n"
    s = raw.decode("utf-8").replace("\r\n", "\n")

    s = patch_once(s, OLD1, NEW1, "apply_experts_nocache")
    s = patch_once(s, OLD2, NEW2, "fd_for")

    open(P, "wb").write(s.replace("\n", eol).encode("utf-8"))
    print(f"done: {P} (eol={eol!r} preserved)")


if __name__ == "__main__":
    main()
