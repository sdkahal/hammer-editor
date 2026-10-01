#!/usr/bin/env python3
"""校验 zh-CN 翻译文件能否安全覆盖到上游源码上。

用法：verify-translations.py <翻译目录> <上游源码目录>

翻译目录下的路径与上游仓库完全一致（这是 `cp -r` 覆盖方案的前提），
所以这里对每一类翻译做两件事：

1. 结构检查 —— XML 能否解析、文件是否存在。上游新增了 strings_*.xml 而翻译
   目录里没有时，Compose/Android 会静默回退到英文，必须当成错误报出来。
2. key 集合比对 —— 翻译的 key 必须与英文源**完全相同**。少了会回退英文，
   多了则是上游已删除的废弃 key，Android 构建期会直接报 duplicate resource。

服务端 properties 同样比对 key。fastlane 文本不比对（自由文本，且不参与构建）。

退出码非 0 表示校验失败，CI 会中止，不进入耗时的构建步骤。
"""

import os
import re
import sys
import xml.etree.ElementTree as ET

# 翻译目录 -> 上游源码目录，按目录名成对映射
XML_DIRS = [
    (
        "common/src/commonMain/composeResources/values-zh-rCN",
        "common/src/commonMain/composeResources/values",
    ),
    (
        "android/src/main/res/values-zh-rCN",
        "android/src/main/res/values",
    ),
]

SERVER_PROPERTIES = "server/src/main/resources/i18n"

errors = []
warnings = []


def xml_keys(path):
    """返回 XML 里所有 <string name="..."> 的 name 集合，解析失败抛异常。"""
    root = ET.parse(path).getroot()
    return {
        el.attrib["name"]
        for el in root.iter("string")
        if "name" in el.attrib
    }


def property_keys(path):
    """返回 .properties 的 key 集合，忽略空行与注释。

    与 Java 的 Properties 语义保持一致：按第一个未转义的 `=` 或 `:` 切分。
    """
    keys = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            stripped = line.lstrip()
            if not stripped or stripped.startswith(("#", "!")):
                continue
            match = re.match(r"([^=:]+)[=:]", line)
            if match:
                keys.add(match.group(1).strip())
    return keys


def report(label, missing, extra):
    if missing:
        errors.append(
            f"{label}: 缺少 {len(missing)} 个 key（会回退显示英文）: "
            + ", ".join(sorted(missing)[:10])
            + (" ..." if len(missing) > 10 else "")
        )
    if extra:
        # 上游删掉的 key 留在翻译里会让 Android 构建期报重复资源，直接当错误。
        errors.append(
            f"{label}: 多出 {len(extra)} 个上游已不存在的 key（会导致构建失败）: "
            + ", ".join(sorted(extra)[:10])
            + (" ..." if len(extra) > 10 else "")
        )


def verify_xml_dir(translation_root, source_root):
    source_dir = os.path.join(source_root, "values")
    translation_dir = os.path.join(translation_root, "values-zh-rCN")

    # 只校验字符串资源：values/ 下还有 colors.xml、ic_launcher_background.xml
    # 这类不参与翻译的资源，Crowdin 的源配置也只收 strings*.xml。
    source_files = {
        name
        for name in os.listdir(source_dir)
        if name.startswith("strings") and name.endswith(".xml")
    }
    if not source_files:
        errors.append(f"{translation_dir}: 上游 {source_dir} 下没有找到 strings*.xml")
        return

    translation_files = {
        name
        for name in os.listdir(translation_dir)
        if name.startswith("strings") and name.endswith(".xml")
    }

    for name in sorted(source_files - translation_files):
        errors.append(f"翻译缺少整个文件: {name}")

    for name in sorted(translation_files - source_files):
        errors.append(f"翻译多出整个文件（上游已不存在）: {name}")

    for name in sorted(source_files & translation_files):
        source_path = os.path.join(source_dir, name)
        translation_path = os.path.join(translation_dir, name)
        try:
            source = xml_keys(source_path)
        except ET.ParseError as exc:
            errors.append(f"上游源文件解析失败 {source_path}: {exc}")
            continue
        try:
            translation = xml_keys(translation_path)
        except ET.ParseError as exc:
            errors.append(f"翻译文件 XML 格式错误 {translation_path}: {exc}")
            continue
        report(name, source - translation, translation - source)


def verify_server_properties(translation_root, source_root):
    source_path = os.path.join(source_root, "Messages_en.properties")
    translation_path = os.path.join(
        translation_root, "Messages_zh_CN.properties"
    )

    # 服务端靠文件名的 locale 段识别语言（ResUtils.getTranslatedLocales 的正则
    # `Messages_([a-zA-Z]{2}(_[A-Z]{2})?)\.properties`），所以文件名本身就是 API 契约。
    if not os.path.exists(translation_path):
        errors.append("翻译缺少 server/src/main/resources/i18n/Messages_zh_CN.properties")
        return
    if not re.match(r"^Messages_[a-zA-Z]{2}(_[A-Z]{2})?\.properties$",
                    os.path.basename(translation_path)):
        errors.append(
            f"服务端翻译文件名 {os.path.basename(translation_path)} 不符合服务端 locale 命名约定"
        )

    report(
        "Messages_zh_CN.properties",
        property_keys(source_path) - property_keys(translation_path),
        property_keys(translation_path) - property_keys(source_path),
    )


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    translation_root, source_root = sys.argv[1], sys.argv[2]

    for translation_dir, _ in XML_DIRS:
        if not os.path.isdir(os.path.join(translation_root, translation_dir)):
            errors.append(f"翻译目录不存在: {translation_dir}")
    if errors:
        for message in errors:
            print(f"::error::{message}")
        return 1

    for translation_dir, source_dir in XML_DIRS:
        verify_xml_dir(
            os.path.join(translation_root, os.path.dirname(translation_dir)),
            os.path.join(source_root, os.path.dirname(source_dir)),
        )

    verify_server_properties(
        os.path.join(translation_root, SERVER_PROPERTIES),
        os.path.join(source_root, SERVER_PROPERTIES),
    )

    for message in warnings:
        print(f"::warning::{message}")
    for message in errors:
        print(f"::error::{message}")

    if errors:
        print(f"\n翻译校验失败：{len(errors)} 个问题")
        return 1

    print("翻译校验通过：所有 key 与上游英文源一一对应。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
