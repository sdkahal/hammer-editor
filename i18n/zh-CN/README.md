# 简体中文翻译（zh-CN）

Hammer 官方使用 [Crowdin](https://crowdin.com) 管理 i18n，翻译不进 Crowdin 平台，
而是以文件形式存放在本目录，由 `.github/workflows/build-zh-cn-release.yml`
在构建时覆盖到上游源码上。

## 目录约定

本目录下的路径与上游仓库 [Darkrock-Studios/hammer-editor](https://github.com/Darkrock-Studios/hammer-editor)
**完全一致**，因此 CI 只需一条 `cp -r` 即可完成覆盖，不需要任何路径映射表：

| 本目录 | 覆盖到上游 |
|---|---|
| `common/src/commonMain/composeResources/values-zh-rCN/` | 同路径 |
| `android/src/main/res/values-zh-rCN/` | 同路径 |
| `server/src/main/resources/i18n/Messages_zh_CN.properties` | 同路径 |
| `fastlane/metadata/android/zh-CN/` | 同路径 |

`values-zh-rCN` 是 Crowdin 的 Android language code（`r` 是地区分隔符），
与仓库里已有的 `values-pt-rBR` 同一套命名规则。Android 系统语言「简体中文」
即 `zh-CN`，会命中该目录。

## 更新翻译

1. 在 Crowdin 下载 `zh-CN` 的翻译包
2. 覆盖本目录下对应文件，注意目录名保持 `values-zh-rCN`
3. 提交并推送 `i18n/zh-cn` 分支，CI 会自动重新构建

上游新增了 string 之后，本目录的翻译会缺 key。构建不会失败（会回退显示英文），
但 `verify` job 会列出缺失的 key，请据此补齐。

## 签名

CI 用仓库 secret `KEY_KEYSTORE_BASE64` / `KEY_STORE_PASSWORD` / `KEY_KEY_ALIAS` /
`KEY_KEY_PASSWORD` 中的自建 keystore 对 Android release 构建签名。
该 keystore 与 Hammer 官方签名不同，因此**无法覆盖安装官方版**，
首次安装前需先卸载官方 Hammer（包名相同、签名不同）。
