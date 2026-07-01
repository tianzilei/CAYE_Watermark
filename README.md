# CAYE Watermark

一个用于单张低分辨率 `DNG` 原始照片修复、放大并导出品牌 `PNG` 的 Python 项目。

## 功能

- 输入仅支持 `DNG`
- 会在解码后自动做左右镜像修正，匹配当前相机的 DNG 写入方向
- 默认使用 `balanced` 修复配置，优先忠实原片
- 默认 `4x` 放大，适合 `644x480` 这类低分辨率 DNG
- 针对存储噪声、细节、锐度、色偏和边缘异常做综合修复
- 包含温和的自动调优曲线，改善低动态范围原片的亮度层次
- 解码后会先在 `16-bit -> float` 工作空间里处理，再导出 `PNG`
- 保留 3 个 `logo-only` 强品牌模板，并新增适合 GUI 驱动的页脚版式模板
- 输出固定为单个 `PNG` 文件；带水印默认命名为 `原文件名_watermarked.png`
- 无水印审片导出默认命名为 `原文件名_review.png`
- 页脚按用户手工填写的 EXIF 风格字段渲染，缺失字段会自动重排布局
- CLI 会实时显示处理阶段，方便后续扩展 GUI

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

## 快速开始

使用内置打包的 `CAYE.webp` 默认水印，处理 `Example/Raw` 中的单张 `DNG`：

```bash
caye-watermark \
  --input-file Example/Raw/CDI_12.DNG \
  --template logo-stamp
```

指定输出文件和模板：

```bash
caye-watermark \
  --input-file Example/Raw/CDI_13.DNG \
  --output-file exports/sample_watermarked.png \
  --template standard-footer \
  --camera-model "Leica Q2" \
  --lens-model "Summilux 28mm" \
  --focal-length-35mm "28mm" \
  --aperture 1.7 \
  --shutter-speed "1/125" \
  --iso 200 \
  --captured-at "2026-06-30 18:40" \
  --upscale-factor 4 \
  --restoration-profile balanced
```

## 常用参数

- `--input-file`：输入文件
- `--output-file`：输出 `PNG` 文件；不传时会按当前模式自动生成
- `--template`：内置水印模板名
- `--watermark-image`：Logo 路径；默认优先使用包内置的 `CAYE.webp`
- `--upscale-factor`：放大倍数，可选 `1`、`2`、`4`，默认 `4`
- `--restoration-profile`：修复配置，可选 `detail`、`balanced`、`clean`
- `--watermark-scale`：Logo 宽度占输出图宽度比例，默认 `0.22`
- `--opacity`：Logo 透明度，范围 `0-255`
- `--camera-model` / `--lens-model`：手工填写页脚的器材信息
- `--focal-length-35mm` / `--aperture` / `--shutter-speed` / `--iso`：手工填写拍摄参数
- `--captured-at`：手工填写拍摄时间
- `--quiet`：关闭实时处理进度输出

## 模板

- `logo-stamp`：左下角实底徽章，默认模板，品牌感最强
- `logo-chip`：左下角深色圆角底板，适合更现代的视觉
- `logo-outline`：左下角细边框包裹，适合稍微克制一点的品牌感
- `standard-footer`：经典白底页脚，适合展示手填 EXIF 信息
- `standard-footer-2`：更宽松的页边距版本，适合信息稍少的情况
- `center-logo`：底栏居中 Logo 模板，适合不展示 EXIF 信息的导出

这 3 个模板是当前仓库里的内置实现。`standard-footer` 和 `standard-footer-2` 会根据用户填写了哪些字段自动折叠空行和重排布局，适合后续 GUI 直接绑定表单输入。

## 移植说明

当前仓库只参考了 `semi-utils` 的模板设计风格，没有移植它的模板引擎或处理器体系。

- 已参考：白底页脚、左右信息分栏、分隔线、底栏居中 Logo 这些视觉布局
- 已保留：原仓库的 `logo-stamp`、`logo-chip`、`logo-outline` 三个 logo-only 模板
- 未移植：`semi-utils` 的 JSON 模板加载、processor 链、EXIF 字段绑定和通用渲染框架

也就是说，这里不是“兼容 `semi-utils` 模板文件”的实现，而是“采用相近视觉语言”的内置模板预设。

## GUI 方向

当前项目的核心目标是保持后端尽量简单，把交互重心留给 GUI。

- 图片处理管线只负责恢复、放大、加水印
- 页脚模板只接受用户手工填写的 EXIF 风格字段，不做自动提取
- 缺失字段时由布局层自动折叠空位，GUI 不需要自己写排版分支

后续如果接 GUI，推荐直接把表单字段映射到这些值：

- `camera_model`
- `lens_model`
- `focal_length_35mm`
- `aperture`
- `shutter_speed`
- `iso`
- `captured_at`

## 修复配置

- `detail`：保留更多纹理，降噪较轻
- `balanced`：降噪和细节折中，默认推荐
- `clean`：更强降噪，更干净但更柔和

## 色偏检测

- 处理流程会自动检测偏暖、偏冷、偏绿、偏洋红等色偏倾向
- `balanced` 默认会做轻量色偏校正，尽量保持原片观感
- CLI 实时状态会显示检测结果，后续 GUI 可以直接复用这部分信息

## 边缘修复

- 解码后会自动检测异常边缘列，并对类似坏色块这类原始伪影做保尺寸修复
- 当前样本里 `CDI_12` 会自动修复右侧异常列，同时保持 `4x` 输出尺寸一致

## 输出规则

- 输入只接受 `.dng`
- 未指定 `--output-file` 时，带水印默认输出 `*_watermarked.png`
- 未指定 `--output-file` 且使用 `--no-watermark` 时，默认输出 `*_review.png`
- 如果显式指定输出文件，扩展名必须是 `.png`
- WebUI 导出文件会默认保存到用户目录下的 `Downloads/caye_exports`

## 实时状态

默认运行时会输出 6 个阶段：

- `load`：读取图片
- `restore`：修复存储伪影、边缘异常并检测色偏
- `superres`：执行超分辨率细节重建
- `watermark`：应用模板
- `export`：导出结果
- `done`：完成保存

这套阶段事件已经独立到了处理管线里，后续如果要做 GUI，可以直接复用同一套状态回调。

## 示例

处理单张 `DNG`，使用默认 `4x + balanced + logo-stamp`：

```bash
caye-watermark --input-file Example/Raw/CDI_12.DNG
```

使用更克制的边框模板：

```bash
caye-watermark \
  --input-file Example/Raw/CDI_15.DNG \
  --template logo-outline \
  --output-file exports/CDI_15_watermarked.png
```

使用 `semi-utils` 风格的页脚模板：

```bash
caye-watermark \
  --input-file Example/Raw/CDI_16.DNG \
  --template standard-footer \
  --camera-model "Leica Q2" \
  --lens-model "Summilux 28mm" \
  --focal-length-35mm "28mm" \
  --aperture 1.7 \
  --shutter-speed "1/125" \
  --iso 200 \
  --captured-at "2026-06-30 18:40" \
  --output-file exports/CDI_16_footer.png
```
